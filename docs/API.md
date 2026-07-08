# API 约定

后端默认地址：`http://localhost:8000/api`

## 游客登录

`POST /auth/visitor-login`

请求：

```json
{
  "nickname": "游客001",
  "interest": "历史文化"
}
```

返回：

```json
{
  "access_token": "jwt-token",
  "token_type": "bearer",
  "user": {
    "id": 2,
    "role": "visitor",
    "nickname": "游客001",
    "username": null,
    "interest": "历史文化"
  }
}
```

## 管理员登录

`POST /auth/admin-login`

请求：

```json
{
  "username": "admin",
  "password": "123456"
}
```

返回：

```json
{
  "access_token": "jwt-token",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "role": "admin",
    "nickname": "系统管理员",
    "username": "admin",
    "interest": null
  }
}
```

## 当前用户

`GET /auth/me`

请求头：

```http
Authorization: Bearer <jwt-token>
```

返回当前登录用户信息。
