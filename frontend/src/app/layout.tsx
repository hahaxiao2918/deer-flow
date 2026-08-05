import "katex/dist/katex.min.css";
import "streamdown/styles.css";
import "@/styles/globals.css";

import { type Metadata } from "next";

import { ThemeProvider } from "@/components/theme-provider";
import { I18nProvider } from "@/core/i18n/context";
import { detectLocaleServer } from "@/core/i18n/server";

// paint 前读门户字号 cookie 设 zoom (跨板块整页缩放, 无 FOUC); 标准档无 cookie → 原始字号。
const FONT_SCALE_INIT = `(function(){try{var m=/ipf_font_scale=([0-9.]+)/.exec(document.cookie);if(m){var s=parseFloat(m[1]);if(s>1){document.documentElement.style.zoom=String(s);}}}catch(e){}})();`;


export const metadata: Metadata = {
  title: "SynForge·思铸",
  description: "一个面向复杂工作的超级 Agent。",
  icons: {
    icon: [
      {
        url: "/images/branding/shanghai-electric-symbol.png",
        type: "image/png",
      },
    ],
  },
};

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const locale = await detectLocaleServer();
  return (
    <html lang={locale} suppressContentEditableWarning suppressHydrationWarning>
      <body>
        <script dangerouslySetInnerHTML={{ __html: FONT_SCALE_INIT }} />
        {/* 返回门户 — 跨板块统一悬浮按钮, 相对路径 / 回同源门户首页 */}
        <a href="https://ipf.nebula-starlink.shanghai-electric.com/" title="返回智海门户首页" style={{position:"fixed",top:10,right:14,zIndex:99999,padding:"5px 12px",fontSize:12,lineHeight:"1.4",color:"#fff",background:"rgba(0,118,184,0.92)",borderRadius:14,textDecoration:"none",boxShadow:"0 2px 8px rgba(0,0,0,0.18)",fontFamily:"system-ui,-apple-system,sans-serif"}}>← 返回门户</a>
        <ThemeProvider attribute="class" enableSystem disableTransitionOnChange>
          <I18nProvider initialLocale={locale}>{children}</I18nProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
