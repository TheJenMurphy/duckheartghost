export default function PrivacyPage() {
  return (
    <div style={{
      maxWidth: 680,
      margin: "0 auto",
      padding: "60px 24px",
      fontFamily: "'Outfit', sans-serif",
      color: "rgba(255,255,255,.85)",
      background: "#000",
      minHeight: "100dvh",
    }}>
      <div style={{ fontSize: ".75rem", fontFamily: "'Space Mono', monospace", color: "#ff8c2a", textTransform: "uppercase", letterSpacing: ".1em", marginBottom: 16 }}>
        Legal
      </div>

      <h1 style={{ fontSize: "2.2rem", fontWeight: 900, letterSpacing: "-.02em", marginBottom: 8, lineHeight: 1.1 }}>
        Privacy Policy
      </h1>

      <p style={{ fontSize: ".85rem", color: "rgba(255,255,255,.4)", marginBottom: 48, fontFamily: "'Space Mono', monospace" }}>
        Last updated: March 2026
      </p>

      <Section title="The short version">
        <p>Duck Heart Ghost collects the minimum data needed to work. We don't sell your data. We don't share your individual votes with brands or retailers. Your Ghost votes are private — they are never visible to other users, brands, or anyone else.</p>
      </Section>

      <Section title="What we collect">
        <p>When you create an account:</p>
        <ul>
          <li>Email address</li>
          <li>Password (encrypted — we never see it)</li>
        </ul>
        <p>When you use the platform:</p>
        <ul>
          <li>Your Duck, Heart, and Ghost votes</li>
          <li>Products you've saved</li>
          <li>Preferences set during onboarding</li>
        </ul>
        <p>Automatically:</p>
        <ul>
          <li>Basic analytics (page views, session data via Vercel Analytics)</li>
          <li>Standard server logs</li>
        </ul>
      </Section>

      <Section title="What we don't collect">
        <ul>
          <li>We do not collect payment information (no purchases happen on DHG)</li>
          <li>We do not build advertising profiles</li>
          <li>We do not track you across other websites</li>
        </ul>
      </Section>

      <Section title="Your Ghost votes">
        <p>Ghost votes are personal filter signals — they tell DHG what to hide from your feed. They are:</p>
        <ul>
          <li>Never shown to other users</li>
          <li>Never shared with brands or retailers</li>
          <li>Never used in community percentage displays</li>
          <li>Only used to personalize your own experience</li>
        </ul>
        <p>We may use aggregated, anonymized Ghost data (e.g. "X% of users filtered out this product") for internal product improvement only.</p>
      </Section>

      <Section title="Affiliate links & conflict of interest">
        <p>Duck Heart Ghost earns a commission when you purchase through retailer links on product cards. This relationship is disclosed on every single card — because that's the whole point.</p>
        <p>When you click an affiliate link, the retailer may set their own cookies and collect data per their own privacy policy. We don't control that.</p>
        <p>DHG will never accept payment from brands to influence how their products are presented, rated, or ranked.</p>
      </Section>

      <Section title="How we store your data">
        <p>Your account data is stored in Supabase, a secure cloud database. Votes and preferences are stored server-side and tied to your account. We use industry-standard encryption in transit and at rest.</p>
      </Section>

      <Section title="Your rights">
        <ul>
          <li><strong>Access:</strong> You can request a copy of your data at any time</li>
          <li><strong>Deletion:</strong> You can delete your account and all associated data</li>
          <li><strong>Correction:</strong> You can update your email and preferences in your account settings</li>
          <li><strong>Portability:</strong> You can request your vote history in a readable format</li>
        </ul>
        <p>To exercise any of these rights, email us at <a href="mailto:hello@duckheartghost.com" style={{ color: "#ff8c2a" }}>hello@duckheartghost.com</a></p>
      </Section>

      <Section title="Children">
        <p>Duck Heart Ghost is not directed at children under 13. We do not knowingly collect data from children under 13. If you believe a child has provided us data, contact us and we will delete it.</p>
      </Section>

      <Section title="Changes to this policy">
        <p>If we make material changes we'll notify you by email or with a notice on the platform. The date at the top of this page always reflects the most recent update.</p>
      </Section>

      <Section title="Contact">
        <p>Questions? <a href="mailto:hello@duckheartghost.com" style={{ color: "#ff8c2a" }}>hello@duckheartghost.com</a></p>
      </Section>

    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 48 }}>
      <h2 style={{
        fontSize: "1.1rem",
        fontWeight: 700,
        color: "#44ddee",
        textTransform: "uppercase",
        letterSpacing: ".05em",
        marginBottom: 16,
        fontFamily: "'Space Mono', monospace",
        fontSize: ".8rem",
      }}>
        {title}
      </h2>
      <div style={{
        fontSize: ".95rem",
        lineHeight: 1.8,
        color: "rgba(255,255,255,.75)",
      }}>
        {children}
      </div>
    </div>
  );
}
