import { supabase } from "./supabase-browser";

export async function resolveAvatarUrl(avatarPath?: string | null): Promise<string | null> {
  if (!avatarPath) return null;
  if (avatarPath.startsWith("http://") || avatarPath.startsWith("https://")) {
    return avatarPath;
  }

  const { data, error } = await supabase.storage.from("avatars").createSignedUrl(avatarPath, 3600);
  if (error || !data?.signedUrl) {
    return null;
  }
  return data.signedUrl;
}
