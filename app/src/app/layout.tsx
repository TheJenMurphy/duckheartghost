import type { Metadata } from "next";
import { Outfit, Space_Mono } from "next/font/google";
import "./globals.css";

const outfit = Outfit({ subsets: ["latin"], variable: "--font-outfit" });
const spaceMono = Space_Mono({ subsets: ["latin"], weight: ["400", "700"], variable: "--font-space-mono" });

export const metadata: Metadata = {
  title: "Duck Heart Ghost — Clean Beauty, Finally Honest",
  description: "Discover clean beauty products without the BS. Duck, Heart, or Ghost every product. Conflicts of interest disclosed on every card.",
  metadataBase: new URL("https://duckheartghost.com"),
  openGraph: {
    title: "Duck Heart Ghost",
    description: "Clean beauty discovery — finally honest. Duck 🦆 Heart ❤️ Ghost 👻",
    url: "https://duckheartghost.com",
    siteName: "Duck Heart Ghost",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Duck Heart Ghost — Clean Beauty Discovery",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Duck Heart Ghost",
    description: "Clean beauty discovery — finally honest. Duck 🦆 Heart ❤️ Ghost 👻",
    images: ["/og-image.png"],
  },
  icons: {
    icon: "/favicon.ico",
    apple: "/apple-touch-icon.png",
  },
  keywords: [
    "clean beauty",
    "non-toxic beauty",
    "beauty product discovery",
    "ingredient transparency",
    "EWG verified",
    "clean skincare",
    "clean makeup",
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${outfit.variable} ${spaceMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
