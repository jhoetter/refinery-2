import "./globals.css";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="top">
          <div>
            <h1>refinery-2</h1>
            <p className="sub">label with teachers · distill to students · serve via API</p>
          </div>
          <nav>
            <a href="/">overview</a>
            <a href="/review">review</a>
            <a href="/templates">templates</a>
            <a href="/models">models</a>
          </nav>
        </header>
        <main>{children}</main>
        <div id="toast" style={{ display: "none" }} />
      </body>
    </html>
  );
}
