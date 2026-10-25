import type { PaginatedData } from "@/utils/helpers";

const BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "https://api.seplume.com/api/v1";

console.log("API Base URL:", BASE_URL);

let isHandling401 = false;
let hasLoggedOut = false;

function buildQuery(params?: Record<string, any>): string {
  if (!params) return "";
  const parts = Object.entries(params)
    .filter(([_, v]) => v !== undefined && v !== null && v !== "")
    .map(
      ([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`,
    );
  return parts.length > 0 ? "?" + parts.join("&") : "";
}

interface ApiResponse<T = any> {
  code: number;
  data: T;
  msg: string;
}

/**
 * 构造可携带 HTTP 状态码的错误对象（F6.11）。
 * 仅增量附加 statusCode 属性，不改变 reject 类型与其他方法行为：
 * 页面可据此区分 403（无权查看）/ 404（不存在）等分支展示不同文案。
 */
function createRequestError(
  message: string,
  statusCode?: number,
): Error & { statusCode?: number } {
  const error = new Error(message) as Error & { statusCode?: number };
  if (statusCode !== undefined) {
    error.statusCode = statusCode;
  }
  return error;
}

/**
 * miniapp 实际使用的 HTTP 动词。
 * 后端契约含 PATCH（users / courses / schedules / teachers 更新接口），
 * 而 @dcloudio/types 的 RequestOptions.method 内联联合
 * （'OPTIONS'|'GET'|'HEAD'|'POST'|'PUT'|'DELETE'|'TRACE'|'CONNECT'）漏声明 PATCH；
 * uni.request 在微信运行时透传 method 字符串，PATCH 可用（上述更新接口既有调用已依赖此行为），
 * 故在 uni.request 调用边界做一次局部断言（见 request 实现），不改变任何运行时行为。
 */
type HttpMethod = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

/** 与 @dcloudio/types RequestOptions.method 联合保持一致，仅用于局部断言 */
type UniCompatibleRequestMethod =
  | "OPTIONS"
  | "GET"
  | "HEAD"
  | "POST"
  | "PUT"
  | "DELETE"
  | "TRACE"
  | "CONNECT";

/** 租户配置 GET /tenant/settings（后端 TenantService.get_settings） */
export interface TenantSettings {
  booking_cancel_minutes: number;
  booking_advance_days: number;
}

/** 租户信息 GET /tenant/info（后端 TenantService.get_tenant_info） */
export interface TenantInfo {
  id: number;
  name: string;
  slug: string;
  logo_url: string | null;
  contact_phone: string | null;
  contact_email: string | null;
}

/** AI 历史消息项 GET /ai/history（会话中角色仅 user / assistant） */
export interface AiChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
}

/** AI 对话响应 data POST /ai/chat */
export interface AiChatResult {
  response: string;
  session_id: string;
  timestamp: string;
  has_pending_state: boolean;
  latency_ms: number;
}

/** 排期详情 GET /schedules/{id}，字段对齐后端 ScheduleResponse */
export interface ScheduleDetail {
  id: number;
  public_id: string;
  tenant_id: number;
  course_id: number;
  teacher_id: number;
  classroom_id: number | null;
  start_at: string;
  end_at: string;
  capacity: number;
  booked_count: number;
  booking_opens_at: string | null;
  booking_closes_at: string | null;
  cancel_deadline: string | null;
  status: number;
  display_status: number;
  notes: string | null;
  preview_content: string | null;
  preview_updated_at: string | null;
  cancel_reason: string | null;
  cancelled_by: number | null;
  cancelled_at: string | null;
  created_at: string;
  updated_at: string;
  teacher_name: string | null;
  course_name: string | null;
  classroom_name: string | null;
  course_type_code: string | null;
}

/** 教师列表项 GET /teachers/（仅声明 miniapp 实际消费字段） */
export interface TeacherListItem {
  id: number;
  nickname?: string;
  avatar_url?: string;
  title?: string;
  specialties?: string[];
}

/** 教师端工作台统计（teacher/profile 页面消费结构） */
export interface TeacherStats {
  courses: number;
  schedules: number;
  students: number;
}

/**
 * 创建带超时的 Promise 包装器
 * 防止 Promise 永远挂起导致 timeout 错误
 * 超时后会自动 abort 底层 uni.request，避免回调泄漏
 */
function withTimeout<T>(
  promise: Promise<T>,
  ms: number,
  errorMessage?: string,
  abortFn?: () => void,
): Promise<T> {
  let timerId: ReturnType<typeof setTimeout>;

  const timeoutPromise = new Promise<never>((_, reject) => {
    timerId = setTimeout(() => {
      abortFn?.();
      reject(new Error(errorMessage || `操作超时 (${ms}ms)`));
    }, ms);
  });

  return Promise.race([
    promise.then(
      (result) => {
        clearTimeout(timerId);
        return result;
      },
      (err) => {
        clearTimeout(timerId);
        throw err;
      },
    ),
    timeoutPromise,
  ]);
}

async function refreshToken(): Promise<boolean> {
  const storedRefreshToken = uni.getStorageSync("refresh_token");
  if (!storedRefreshToken) return false;

  const tenantSlug = uni.getStorageSync("tenant_slug");
  const header: Record<string, string> = { "Content-Type": "application/json" };
  if (tenantSlug) {
    header["x-tenant-slug"] = tenantSlug;
  }

  try {
    let refreshTask: ReturnType<typeof uni.request> | null = null;
    const result = await withTimeout(
      new Promise<ApiResponse>((resolve, reject) => {
        refreshTask = uni.request({
          url: `${BASE_URL}/auth/refresh-token`,
          method: "POST",
          header,
          data: { refresh_token: storedRefreshToken },
          timeout: 5000, // ✅ 新增：5秒超时
          success: (res) => resolve(res.data as ApiResponse),
          fail: (err) => reject(err),
        });
      }),
      6000, // ✅ 新增：Promise 总超时 6秒
      "刷新 Token 超时",
      () => refreshTask?.abort(),
    );

    if (result.code === 0 || result.code === 200) {
      uni.setStorageSync("token", result.data.access_token);
      uni.setStorageSync("refresh_token", result.data.refresh_token);
      return true;
    }
    return false;
  } catch (error) {
    console.warn("刷新 Token 失败:", error);
    return false;
  }
}

async function request<T>(
  url: string,
  method: HttpMethod = "GET",
  data?: any,
  headers?: any,
  showError: boolean = true,
  retryCount: number = 0,
): Promise<ApiResponse<T>> {
  const token = uni.getStorageSync("token");
  let tenantSlug = uni.getStorageSync("tenant_slug");

  // 首次登录时，storage 中可能还没有 tenant_slug，尝试从请求 body 中获取
  if (!tenantSlug && data && typeof data === "object" && data.tenant_slug) {
    tenantSlug = data.tenant_slug;
  }

  // 🆕 防御性措施：如果仍然没有 tenant_slug，使用默认值（防止 40001 错误）
  if (!tenantSlug) {
    tenantSlug = "dance-school";
    console.warn("⚠️ [API] 未找到 tenant_slug，使用默认值: dance-school");
  }

  const defaultHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token && { Authorization: `Bearer ${token}` }),
    ...(tenantSlug && { "x-tenant-slug": tenantSlug }),
  };

  const isLoginRequest =
    url.includes("/auth/login") ||
    url.includes("/auth/wechat-login") ||
    url.includes("/auth/wechat-auto-login") ||
    url.includes("/auth/register") ||
    url.includes("/auth/refresh-token") ||
    url.includes("/auth/logout") ||
    url.includes("/auth/wechat-unbind");

  if (isLoginRequest) {
    hasLoggedOut = false;
    isHandling401 = false;
  }

  const requestTimeout = isLoginRequest ? 10000 : 30000;
  const totalTimeout = requestTimeout + 2000; // ✅ Promise 总超时比请求超时多 2 秒

  let requestTask: ReturnType<typeof uni.request> | null = null;

  return withTimeout(
    new Promise<ApiResponse<T>>((resolve, reject) => {
      const fullUrl = `${BASE_URL}${url}`;
      console.log(`API请求: ${method} ${fullUrl}`, data || "");

      requestTask = uni.request({
        url: fullUrl,
        // 第三方 @dcloudio/types 联合漏 PATCH，见 HttpMethod 注释；局部断言、运行时原样透传
        method: method as UniCompatibleRequestMethod,
        data,
        header: { ...defaultHeaders, ...headers },
        timeout: requestTimeout,
        success: async (res) => {
          const result = res.data as ApiResponse<T>;
          console.log(
            `API响应: ${method} ${url}`,
            res.statusCode,
            JSON.stringify(result),
          );

          if (result.code === 401 && !isLoginRequest && retryCount === 0) {
            try {
              const refreshed = await refreshToken();
              if (refreshed) {
                // 显式透传泛型 T，保证重放请求与原请求响应类型一致
                const retryResult = await request<T>(
                  url,
                  method,
                  data,
                  headers,
                  showError,
                  retryCount + 1,
                );
                resolve(retryResult);
                return;
              }
            } catch (retryError) {
              console.warn("重试失败:", retryError);
            }
          }

          if (result.code === 401) {
            if (isLoginRequest) {
              reject(new Error(result.msg || "登录失败"));
              return;
            }

            if (isHandling401) {
              reject(new Error("登录已过期"));
              return;
            }

            if (hasLoggedOut) {
              reject(new Error("登录已过期"));
              return;
            }

            isHandling401 = true;
            hasLoggedOut = true;

            uni.removeStorageSync("token");
            uni.removeStorageSync("refresh_token");
            uni.removeStorageSync("user_role");
            uni.removeStorageSync("tenant_slug");
            uni.removeStorageSync("user_info");

            uni.showToast({ title: "登录已过期，请重新登录", icon: "none" });

            setTimeout(() => {
              isHandling401 = false;
              const pages = getCurrentPages();
              const currentPage = pages[pages.length - 1];
              if (currentPage && currentPage.route === "pages/index/index") {
                hasLoggedOut = false;
                return;
              }
              uni.reLaunch({ url: "/pages/index/index" });
            }, 1000);

            reject(new Error("登录已过期"));
            return;
          }

          if (result.code !== 0 && result.code !== 200) {
            if (showError) {
              uni.showToast({ title: result.msg || "请求失败", icon: "none" });
            }
            // 附加 HTTP 状态码，供页面区分 403 / 404 等分支（F6.11）
            reject(
              createRequestError(result.msg || "请求失败", res.statusCode),
            );
            return;
          }
          resolve(result);
        },
        fail: (err) => {
          console.error(`API请求失败: ${method} ${url}`, JSON.stringify(err));
          if (showError) {
            const msg = isLoginRequest
              ? "登录失败，请检查网络连接"
              : "网络请求失败，请稍后重试";
            uni.showToast({ title: msg, icon: "none" });
          }
          reject(err);
        },
      });
    }),
    totalTimeout,
    `请求超时: ${method} ${url}`,
    () => requestTask?.abort(),
  );
}

export function resetAuthState() {
  hasLoggedOut = false;
  isHandling401 = false;
}

export function clearAuthData() {
  uni.removeStorageSync("token");
  uni.removeStorageSync("refresh_token");
  uni.removeStorageSync("user_info");
  uni.removeStorageSync("user_role");
  hasLoggedOut = true;
  isHandling401 = false;
}

export const authApi = {
  login(data: { phone: string; password: string; tenant_slug: string }) {
    return request("/auth/login", "POST", data, undefined, false);
  },

  register(data: {
    phone: string;
    nickname: string;
    tenant_slug: string;
    code?: string;
  }) {
    return request("/auth/register", "POST", data, undefined, false);
  },

  logout() {
    const refreshTokenValue = uni.getStorageSync("refresh_token");
    return request("/auth/logout", "POST", {
      refresh_token: refreshTokenValue,
    });
  },

  getMe() {
    return request("/auth/me");
  },

  wechatLogin(data: {
    bind_token: string;
    phone?: string;
    encrypted_data?: string;
    iv?: string;
    tenant_slug: string;
  }) {
    return request("/auth/wechat-login", "POST", data, undefined, false);
  },

  wxAutoLogin(data: { code: string; tenant_slug: string }) {
    return request("/auth/wechat-auto-login", "POST", data, undefined, false);
  },

  sendSms(data: { phone: string; tenant_slug: string; type: string }) {
    return request("/auth/sms", "POST", data, undefined, false);
  },

  /**
   * 绑定微信账号（新用户/未绑定时使用）
   */
  bindAccount(data: {
    bind_token: string;
    openid?: string;
    phone: string;
    sms_code: string;
    role?: "student" | "teacher";
    tenant_slug?: string;
  }) {
    return request("/auth/bind-account", "POST", data, undefined, false);
  },

  wechatUnbind() {
    return request("/auth/wechat-unbind", "POST");
  },
};

export const userApi = {
  updateProfile(
    userId: number,
    data: { nickname?: string; avatar_url?: string },
  ) {
    return request(`/users/${userId}`, "PATCH", data);
  },

  changePassword(
    userId: number,
    data: { old_password: string; new_password: string },
  ) {
    return request(`/users/${userId}/password/change`, "POST", data);
  },

  update(data: { nickname?: string; bio?: string }) {
    return request("/users/me", "PATCH", data);
  },
};

export const courseApi = {
  list(params?: any) {
    const query = buildQuery(params);
    return request(`/courses${query}`);
  },

  get(id: number) {
    return request(`/courses/${id}`);
  },

  create(data: any) {
    return request("/courses/", "POST", data);
  },

  update(id: number, data: any) {
    return request(`/courses/${id}`, "PATCH", data);
  },

  delete(id: number) {
    return request(`/courses/${id}`, "DELETE");
  },
};

export const courseTypeApi = {
  list(params?: any) {
    const query = buildQuery(params);
    return request(`/courses/types${query}`);
  },
};

export const scheduleApi = {
  list(params?: any) {
    const query = buildQuery(params);
    return request(`/schedules${query}`);
  },

  get(id: number) {
    return request<ScheduleDetail>(`/schedules/${id}`);
  },

  create(data: any) {
    return request("/schedules/", "POST", data);
  },

  update(id: number, data: any) {
    return request(`/schedules/${id}`, "PATCH", data);
  },

  cancel(id: number) {
    return request(`/schedules/${id}/cancel`, "POST");
  },
};

export const bookingApi = {
  // 后端 GET /bookings 固定返回分页结构 { items,total,page,page_size }
  list(params?: any) {
    const query = buildQuery(params);
    return request<PaginatedData<any>>(`/bookings${query}`);
  },

  create(data: { schedule_id: number; membership_card_id?: number }) {
    return request("/bookings/", "POST", data);
  },

  cancel(bookingId: number, reason?: string) {
    const query = reason ? `?reason=${encodeURIComponent(reason)}` : "";
    return request(`/bookings/${bookingId}/cancel${query}`, "POST");
  },

  cancelBySchedule(scheduleId: number, reason?: string) {
    return request("/bookings/cancel", "POST", {
      schedule_id: scheduleId,
      reason,
    });
  },

  checkIn(bookingId: number) {
    return request(`/bookings/${bookingId}/check-in`, "POST");
  },

  complete(bookingId: number) {
    return request(`/bookings/${bookingId}/complete`, "POST");
  },

  /**
   * 改期 / 改派（F6.5）。F6.7 换卡场景为同排期纯改派：
   * new_schedule_id 传原排期，new_membership_card_id 传替代卡。
   * idempotencyKey 经 Idempotency-Key 请求头上送，网络重试安全。
   */
  reschedule(
    bookingId: number,
    data: {
      new_schedule_id: number;
      new_membership_card_id?: number | null;
      reason?: string | null;
    },
    idempotencyKey?: string,
  ) {
    const headers = idempotencyKey
      ? { "Idempotency-Key": idempotencyKey }
      : undefined;
    return request(`/bookings/${bookingId}/reschedule`, "POST", data, headers);
  },
};

export const teacherApi = {
  getInfo() {
    return request("/teachers/me");
  },

  updateInfo(data: { title?: string; bio?: string; specialties?: string[] }) {
    return request("/teachers/me", "PATCH", data);
  },

  getCourses(params?: any) {
    const query = buildQuery(params);
    return request(`/courses${query}`);
  },

  getSchedules(params?: any) {
    const query = buildQuery(params);
    return request(`/schedules${query}`);
  },

  // 注意：当前端点为 /auth/me，返回结构与 TeacherStats 的差异为既有实现，
  // 本 Feature 仅按页面消费结构补类型，不改接口与业务逻辑（见交付报告 Risks）。
  getStats() {
    return request<TeacherStats>("/auth/me");
  },

  list() {
    return request<TeacherListItem[]>("/teachers/");
  },
};

export const studentApi = {
  getCourses(params?: any) {
    const query = buildQuery(params);
    return request(`/courses${query}`);
  },

  getStats() {
    return request("/auth/me");
  },

  getInfo() {
    return request("/users/me");
  },

  updateInfo(data: { nickname?: string; bio?: string }) {
    return request("/users/me", "PATCH", data);
  },
};

export const classroomApi = {
  list(params?: any) {
    const query = buildQuery(params);
    return request(`/classrooms${query}`);
  },
};

export const aiChatApi = {
  chat(message: string, session_id: string = "default") {
    return request<AiChatResult>(
      "/ai/chat",
      "POST",
      { message, session_id },
      undefined,
      false,
    );
  },

  getHistory(session_id: string = "default") {
    const query = buildQuery({ session_id });
    return request<AiChatMessage[]>(`/ai/history${query}`);
  },

  clearHistory(session_id: string = "default") {
    return request(`/ai/history`, "DELETE", { session_id });
  },
};

export const membershipApi = {
  getMyCards() {
    return request("/membership/my-cards");
  },

  // 排期推荐可用会员卡（后端统一可用性判定与 D6 排序）
  getRecommendCard(scheduleId: number) {
    return request("/membership/recommend-card", "GET", {
      schedule_id: scheduleId,
    });
  },

  getCardDetail(cardId: number) {
    return request(`/membership/cards/${cardId}`);
  },

  activateCard(cardId: number) {
    return request(`/membership/cards/${cardId}/activate`, "POST");
  },

  studentUnfreeze(cardId: number) {
    return request(`/membership/cards/${cardId}/student-unfreeze`, "POST");
  },

  getTransactions(params?: {
    card_id?: number;
    page?: number;
    page_size?: number;
  }) {
    const query = buildQuery(params);
    return request(`/membership/transactions${query}`);
  },

  // 卡的受影响预约（F6.7；student 仅本人卡可查，主要用于核对场景）
  getAffectedBookings(
    cardId: number,
    params?: { page?: number; page_size?: number },
  ) {
    const query = buildQuery(params);
    return request(`/membership/cards/${cardId}/affected-bookings${query}`);
  },
};

export const tenantApi = {
  getSettings() {
    return request<TenantSettings>("/tenant/settings");
  },
  getInfo() {
    return request<TenantInfo>("/tenant/info");
  },
};
