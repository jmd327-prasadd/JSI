import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "JQA - Quality Analysis",
  description: "Onboarding quality analysis for DBT / Snowflake / Fivetran / Power BI projects",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <Link href="/" className="brand">
            JQA
          </Link>
          <span className="tagline">Managed services onboarding quality analysis</span>
        </header>
        <main className="site-main">{children}</main>
      </body>
    </html>
  );
}
