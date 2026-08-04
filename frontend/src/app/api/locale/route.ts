import { NextResponse } from "next/server";
import { isAppLocale } from "@/i18n/config";
import { LOCALE_COOKIE } from "@/i18n/server";

export async function POST(request: Request) {
  const body = await request.json().catch(() => null);
  if (!body || !isAppLocale(body.locale)) {
    return NextResponse.json({ detail: "Unsupported locale" }, { status: 422 });
  }
  const response = NextResponse.json({ locale: body.locale });
  response.cookies.set({
    name: LOCALE_COOKIE,
    value: body.locale,
    maxAge: 60 * 60 * 24 * 365,
    path: "/",
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    httpOnly: true,
  });
  return response;
}
