"use client";

import { useEffect, useState } from "react";

/**
 * 数字底座 (IPD) SSO front-end interception route (use-case 2).
 *
 * IPD redirects the browser here carrying `code`/`state`/`tenant-id`/
 * `organize-id` after the user authorizes on the portal. This page forwards
 * those parameters to the Gateway's non-OIDC OAuth2 callback, which exchanges
 * the code, provisions the DeerFlow user, sets the session cookie, and
 * redirects to /auth/callback (resolved to /workspace by the (auth) layout).
 *
 * When visited WITHOUT a `code` (the "sso path" entry branch of use-case 2),
 * it starts the flow by redirecting to the Gateway OAuth2 start endpoint,
 * which sets the DeerFlow nonce cookie and redirects to IPD's authorize URL.
 *
 * This route is intentionally NOT under (auth)/ so it does not trigger the
 * server-side /auth/me lookup during the in-flight SSO handoff.
 *
 * See backend/app/gateway/auth/oauth2.py and routers/auth.py (`/oauth2/...`).
 */
export default function LoginSsoPage() {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    // IPD sends tenant-id / organize-id with a hyphen; forward as-is.
    const tenantId = params.get("tenant-id") ?? params.get("tenant_id");
    const organizeId = params.get("organize-id") ?? params.get("organize_id");
    const nextPath = params.get("next") ?? "/workspace";

    const controller = new AbortController();

    void fetch("/api/v1/auth/providers", { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("providers"))))
      .then((data: { providers?: { id: string; type: string }[] }) => {
        const oauth2 = (data.providers ?? []).find((p) => p.type === "oauth2");
        if (!oauth2) {
          window.location.href = "/login?error=sso_failed";
          return;
        }
        if (code) {
          const q = new URLSearchParams({ code });
          if (tenantId) q.set("tenant-id", tenantId);
          if (organizeId) q.set("organize-id", organizeId);
          window.location.href = `/api/v1/auth/oauth2/${encodeURIComponent(oauth2.id)}/callback?${q.toString()}`;
        } else {
          const q = new URLSearchParams({ next: nextPath });
          window.location.href = `/api/v1/auth/oauth2/${encodeURIComponent(oauth2.id)}/start?${q.toString()}`;
        }
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        setFailed(true);
        window.location.href = "/login?error=sso_failed";
      });

    return () => controller.abort();
  }, []);

  return (
    <div className="flex h-screen flex-col items-center justify-center gap-4">
      <p className="text-muted-foreground">
        {failed
          ? "SSO 登录不可用，正在返回登录页…"
          : "正在跳转到数字底座登录…"}
      </p>
    </div>
  );
}
