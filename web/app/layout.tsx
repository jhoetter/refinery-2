import "./globals.css";
import Nav from "./nav";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="top">
          <div>
            <h1>refinery-2</h1>
            <p className="sub">label with teachers · distill to students · serve via API</p>
          </div>
          <Nav />
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
