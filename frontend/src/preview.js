export function resolvePreview(artifacts = {}) {
  if (artifacts.png) return { url: artifacts.png, type: "png" };
  if (artifacts.svg) return { url: artifacts.svg, type: "svg" };
  return { url: "", type: "none" };
}
