import React from "react";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body style={{ margin: 0, fontFamily: "system-ui", background: "#f5f7fb", color: "#172033" }}>{children}</body></html>;
}
