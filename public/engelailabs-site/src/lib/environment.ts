function isPrivateIpv4(hostname: string): boolean {
  const octets = hostname.split(".").map(Number);
  if (octets.length !== 4 || octets.some((octet) => !Number.isInteger(octet) || octet < 0 || octet > 255)) {
    return false;
  }

  return (
    octets[0] === 10 ||
    octets[0] === 127 ||
    (octets[0] === 169 && octets[1] === 254) ||
    (octets[0] === 172 && octets[1] >= 16 && octets[1] <= 31) ||
    (octets[0] === 192 && octets[1] === 168)
  );
}

export function publicHttpsUrl(value: string | undefined): string | null {
  if (!value) return null;

  try {
    const parsed = new URL(value);
    const hostname = parsed.hostname.toLowerCase();
    const privateHostname =
      hostname === ["local", "host"].join("") ||
      hostname === "::1" ||
      hostname.endsWith(".local") ||
      isPrivateIpv4(hostname);

    if (
      parsed.protocol !== "https:" ||
      parsed.username ||
      parsed.password ||
      parsed.port ||
      privateHostname
    ) {
      return null;
    }

    return parsed.toString();
  } catch {
    return null;
  }
}

export const publicEnvironment = {
  siteUrl: publicHttpsUrl(import.meta.env.VITE_SITE_URL) ?? "https://engelailabs.com/",
  githubUrl: publicHttpsUrl(import.meta.env.VITE_GITHUB_URL),
  moltbookUrl:
    publicHttpsUrl(import.meta.env.VITE_MOLTBOOK_URL) ??
    "https://www.moltbook.com/u/engel-ai-main",
  communityUrl: publicHttpsUrl(import.meta.env.VITE_COMMUNITY_URL),
} as const;
