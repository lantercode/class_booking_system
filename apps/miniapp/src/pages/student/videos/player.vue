<template>
  <view class="video-player-page">
    <AppNavbar :title="title" />
    <view class="player-container">
      <video
        :src="videoUrl"
        class="video-player"
        controls
        autoplay
        object-fit="contain"
        @error="onVideoError"
      />
    </view>
  </view>
</template>

<script setup lang="ts">
import { uploadApi } from "@/api";
import AppNavbar from "@/components/AppNavbar.vue";
import { onMounted, ref } from "vue";

const title = ref("视频播放");
const videoUrl = ref("");
const videoKey = ref("");
let refreshed = false;

/** 从预签名 URL 还原 object_key（路径部分即 t/{tenant}/...） */
const deriveObjectKey = (url: string): string => {
  if (!url) return "";
  const noQuery = url.split("?")[0];
  const idx = noQuery.indexOf("/t/");
  return idx >= 0 ? decodeURIComponent(noQuery.slice(idx + 1)) : "";
};

onMounted(() => {
  const pages = getCurrentPages();
  const currentPage = pages[pages.length - 1] as any;
  const options = currentPage.options || {};
  const fallbackTitle = decodeURIComponent(options.title || "视频播放");

  // 优先读取首页写入的缓存（含完整预签名 URL 与 object_key）
  const cached = uni.getStorageSync("pending_video");
  if (cached?.url) {
    videoUrl.value = cached.url;
    videoKey.value = cached.videoKey || deriveObjectKey(cached.url);
    title.value = cached.title || fallbackTitle;
    return;
  }

  title.value = fallbackTitle;
  videoUrl.value = decodeURIComponent(options.url || "");
  videoKey.value = deriveObjectKey(videoUrl.value);
});

/**
 * 播放失败处理：
 * 1. 若是预签名地址过期，用 object_key 换取新地址重试一次；
 * 2. 仍失败则提示具体 errMsg（域名未校验 / 编码不支持 / 403 等）。
 */
const onVideoError = async (e: any) => {
  const errMsg: string = e?.detail?.errMsg || "未知错误";
  console.error("❌ 视频播放失败:", errMsg, videoUrl.value);

  if (!refreshed && videoKey.value) {
    refreshed = true;
    try {
      const res = await uploadApi.getUrl(videoKey.value);
      const newUrl = res.data?.url || "";
      if (newUrl) {
        videoUrl.value = newUrl;
        uni.showToast({ title: "已刷新视频链接", icon: "none" });
        return;
      }
    } catch {
      // 换取失败，走统一错误提示
    }
  }

  uni.showToast({
    title: `视频加载失败：${errMsg}`,
    icon: "none",
    duration: 3000,
  });
};
</script>

<style lang="scss" scoped>
.video-player-page {
  min-height: 100vh;
  background-color: #000;
}

.player-container {
  width: 100%;
  height: calc(100vh - var(--navbar-height));
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #000;
}

.video-player {
  width: 100%;
  height: 100%;
}
</style>
