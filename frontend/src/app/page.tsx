import { redirect } from "next/navigation";

export default function HomePage() {
  // SSO-first entry (数字底座/IPD use-case 2): the domain root starts the SSO
  // flow. /loginsso detects an existing base LTPA session (seamless sign-in) or
  // bounces to the base login page. Local password login remains available at
  // /login (break-glass) and via the fallback link on /loginsso.
  redirect("/loginsso");
}
