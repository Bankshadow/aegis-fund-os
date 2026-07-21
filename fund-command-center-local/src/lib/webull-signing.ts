const encoder = new TextEncoder();

function toBase64(bytes: ArrayBuffer): string {
  const binary = Array.from(new Uint8Array(bytes), (byte) => String.fromCharCode(byte)).join("");
  return btoa(binary);
}

export async function webullHmacSha1Base64(secret: string, payload: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(`${secret}&`),
    { name: "HMAC", hash: "SHA-1" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    encoder.encode(encodeURIComponent(payload)),
  );
  return toBase64(signature);
}

export async function signWebullGetRequest(input: {
  path: string;
  query?: Record<string, string>;
  appKey: string;
  appSecret: string;
  host: string;
  timestamp: string;
  nonce: string;
}): Promise<string> {
  const parameters = {
    ...(input.query ?? {}),
    host: input.host,
    "x-app-key": input.appKey,
    "x-signature-algorithm": "HMAC-SHA1",
    "x-signature-nonce": input.nonce,
    "x-signature-version": "1.0",
    "x-timestamp": input.timestamp,
  };
  const str1 = Object.keys(parameters)
    .sort()
    .map((key) => `${key}=${parameters[key as keyof typeof parameters]}`)
    .join("&");
  return webullHmacSha1Base64(input.appSecret, `${input.path}&${str1}`);
}

export async function signWebullRequest(input: {
  path: string;
  query?: Record<string, string>;
  body: string;
  appKey: string;
  appSecret: string;
  host: string;
  timestamp: string;
  nonce: string;
}): Promise<string> {
  const parameters = {
    ...(input.query ?? {}),
    host: input.host,
    "x-app-key": input.appKey,
    "x-signature-algorithm": "HMAC-SHA1",
    "x-signature-nonce": input.nonce,
    "x-signature-version": "1.0",
    "x-timestamp": input.timestamp,
  };
  const str1 = Object.keys(parameters)
    .sort()
    .map((key) => `${key}=${parameters[key as keyof typeof parameters]}`)
    .join("&");
  // Webull's POST signature includes uppercase MD5(body). MD5 is only used in
  // this server-only module; the browser never receives the signing secret.
  const { createHash } = await import("node:crypto");
  const bodyMd5 = createHash("md5").update(input.body, "utf8").digest("hex").toUpperCase();
  return webullHmacSha1Base64(input.appSecret, `${input.path}&${str1}&${bodyMd5}`);
}
