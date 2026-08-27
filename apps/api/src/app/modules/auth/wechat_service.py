import base64
import json

import httpx
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from app.core.config import get_settings
from app.core.exceptions import AuthException


class WechatService:
    @staticmethod
    def code_to_openid(code: str, app_id: str | None = None):
        settings = get_settings()

        if not app_id:
            app_id = settings.WECHAT_APP_ID

        params = {
            "appid": app_id,
            "secret": settings.WECHAT_SECRET,
            "js_code": code,
            "grant_type": "authorization_code",
        }
        response = httpx.get("https://api.weixin.qq.com/sns/jscode2session", params=params)
        data = response.json()
        print(f"微信接口返回数据：{data}")

        if "errcode" in data and data["errcode"] != 0:
            raise AuthException(f"微信登录失败：{data.get('errmsg', '未知错误')}")

        return {
            "openid": data["openid"],
            "unionid": data.get("unionid", None),
            "session_key": data["session_key"],
        }

    @staticmethod
    def decrypt_phone(encrypted_data: str, iv: str, session_key: str) -> str:
        session_key_bytes = base64.b64decode(session_key)
        iv_bytes = base64.b64decode(iv)
        encrypted_bytes = base64.b64decode(encrypted_data)

        cipher = Cipher(algorithms.AES(session_key_bytes), modes.CBC(iv_bytes))
        decryptor = cipher.decryptor()
        decrypted_padded = decryptor.update(encrypted_bytes) + decryptor.finalize()

        unpadder = padding.PKCS7(128).unpadder()
        decrypted = unpadder.update(decrypted_padded) + unpadder.finalize()

        data = json.loads(decrypted.decode("utf-8"))
        phone = data.get("purePhoneNumber") or data.get("phoneNumber", "")
        if not phone:
            raise AuthException("微信手机号解密失败：未获取到手机号")
        return phone
