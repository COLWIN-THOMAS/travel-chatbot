import { Linking, Platform } from 'react-native';
import type { DeepLink } from './types';

/**
 * Opens a DeepLink: tries the app scheme first (native only — custom schemes don't apply on
 * web), falls back to the web URL if the app isn't installed or there's no app_url at all.
 * `canOpenURL` on a custom scheme requires the scheme to be allow-listed in app.json
 * (ios.infoPlist.LSApplicationQueriesSchemes) to return true even when the app IS installed —
 * without that entry this safely falls through to the web URL, which still works.
 */
export async function openDeepLink(link: DeepLink): Promise<void> {
  if (link.app_url && Platform.OS !== 'web') {
    try {
      const canOpen = await Linking.canOpenURL(link.app_url);
      if (canOpen) {
        await Linking.openURL(link.app_url);
        return;
      }
    } catch {
      // fall through to the web URL
    }
  }
  await Linking.openURL(link.web_url);
}
