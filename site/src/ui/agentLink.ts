import { AGENT_HANDLE, LINKS } from "../config";

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const input = document.createElement("textarea");
    input.value = text;
    input.style.position = "fixed";
    input.style.opacity = "0";
    document.body.append(input);
    try {
      input.select();
      return Boolean(document.execCommand?.("copy"));
    } catch {
      return false;
    } finally {
      input.remove();
    }
  }
}

export function openAgent(prompt: string): Promise<string> {
  const text = prompt.trim();
  const request = new RegExp(`^${AGENT_HANDLE}(?:\\s|$)`, "i").test(text)
    ? text
    : `${AGENT_HANDLE} ${text}`;
  // Start copying while this page still has focus; open during the click itself.
  const copied = copyText(request);
  window.open(LINKS.asiOne, "_blank", "noopener,noreferrer");
  return copied.then((ok) => ok
    ? "Prompt copied. Paste it into BLR Air Window on ASI:One, then send."
    : `Paste this into BLR Air Window on ASI:One: ${request}`);
}
