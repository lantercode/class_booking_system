from typing import Optional


class DanceSaasException(Exception):
    def __init__(self, code: int,  msg: str, errors: Optional[list[str]]=None):
        self.code = code
        self.msg = msg
        self.errors = errors or []

class AuthException(DanceSaasException):
    def __init__(self, msg: str="认证失败，请先登录", errors:Optional[list[str]]=None):
        super().__init__(401, msg, errors)

class PermissionException(DanceSaasException):
    def __init__(self, msg: str="无权限访问", errors:Optional[list[str]]=None):
        super().__init__(403, msg, errors)

class ValidationException(DanceSaasException):
    def __init__(self, msg: str="参数验证失败", errors:Optional[list[str]]=None):
        super().__init__(400, msg, errors)

class NotFoundException(DanceSaasException):
    def __init__(self, msg: str="资源不存在", errors:Optional[list[str]]=None):
        super().__init__(404, msg, errors)

class BusinessException(DanceSaasException):
    def __init__(self, msg: str="业务错误", code: int=500, errors:Optional[list[str]]=None):
        super().__init__(code, msg, errors)

