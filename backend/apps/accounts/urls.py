from django.urls import path

from .api import admin, auth

auth_urls = [
    path("csrf", auth.CsrfView.as_view(), name="csrf"),
    path("login", auth.LoginView.as_view(), name="login"),
    path("register", auth.RegisterView.as_view(), name="register"),
    path("password", auth.PasswordChangeView.as_view(), name="password-change"),
    path("logout", auth.LogoutView.as_view(), name="logout"),
    path("me", auth.MeView.as_view(), name="me"),
    path("sessions", auth.SessionListView.as_view(), name="sessions"),
    path("sessions/revoke-others", auth.RevokeOtherSessionsView.as_view(), name="sessions-revoke-others"),
    path("sessions/<uuid:public_id>", auth.SessionDetailView.as_view(), name="session-detail"),
]

admin_urls = [
    path("roles", admin.RoleListView.as_view(), name="roles"),
    path("staff", admin.StaffListCreateView.as_view(), name="staff"),
    path("staff/<uuid:public_id>", admin.StaffDetailView.as_view(), name="staff-detail"),
    path("users", admin.UserListView.as_view(), name="users"),
    path("users/<uuid:public_id>/activate", admin.UserActivateView.as_view(), name="user-activate"),
    path("users/<uuid:public_id>/deactivate", admin.UserDeactivateView.as_view(), name="user-deactivate"),
    path("users/<uuid:public_id>/set-password", admin.UserSetPasswordView.as_view(), name="user-set-password"),
    path("users/<uuid:public_id>/revoke-sessions", admin.UserRevokeSessionsView.as_view(), name="user-revoke-sessions"),
]
