# -*- coding: utf-8 -*-
from typing import Any, List
from java.lang import Float as JFloat, Boolean as JBoolean, Integer as JInteger
from java import jfloat
from base_plugin import BasePlugin, MethodHook
from hook_utils import find_class
from ui.settings import Switch, Header, Selector, Input, Text, Divider
import time

__id__ = "search_bar_control"
__name__ = "Search Bar Control"
__description__ = "Pins the search bar on the main page and helps collapse stories."
__author__ = "@itNotMax - @MaxExteraPlugins"
__version__ = "4.0.0"
__icon__ = "MaxExteraPluginsStickers/3"
__min_version__ = "12.10.6"
__app_version__ = ">=12.5.1"
__sdk_version__ = ">=1.4.3.3"
min_version = "12.5.1"
app_version = ">=12.5.1"
sdk_version = ">=1.4.3.3"


def to_signed32(v):
    v = v & 0xFFFFFFFF
    if v >= 0x80000000:
        return v - 0x100000000
    return v


def parse_color(hex_str):
    if not hex_str:
        return None
    s = hex_str.strip().lstrip("#")
    try:
        if len(s) == 6:
            r = int(s[0:2], 16)
            g = int(s[2:4], 16)
            b = int(s[4:6], 16)
            return to_signed32((0xFF << 24) | (r << 16) | (g << 8) | b)
        elif len(s) == 8:
            r = int(s[0:2], 16)
            g = int(s[2:4], 16)
            b = int(s[4:6], 16)
            a = int(s[6:8], 16)
            return to_signed32((a << 24) | (r << 16) | (g << 8) | b)
        else:
            return None
    except Exception:
        return None


def unsigned(c):
    if c is None:
        return 0
    return c if c >= 0 else c + 0x100000000


class ScrollYHook(MethodHook):

    def __init__(self, plugin):
        self.plugin = plugin
        self._field_cache = {}
        self._expanded_by_user = False
        self._last_instance = None
        self._dp81 = None
        self._expand_time = 0
        self._style_applied = False
        self._search_dp = None

    def _resolve_field(self, instance, name):
        cls_obj = instance.getClass()
        cache_key = (id(cls_obj), name)
        if cache_key in self._field_cache:
            return self._field_cache[cache_key]
        try:
            cls = cls_obj
            while cls is not None:
                try:
                    f = cls.getDeclaredField(name)
                    f.setAccessible(True)
                    self._field_cache[cache_key] = f
                    return f
                except Exception:
                    cls = cls.getSuperclass()
        except Exception:
            pass
        self._field_cache[cache_key] = None
        return None

    def _get_field(self, instance, name):
        f = self._resolve_field(instance, name)
        if f is not None:
            try:
                return f.get(instance)
            except Exception:
                pass
        return None

    def _set_field(self, instance, name, value):
        f = self._resolve_field(instance, name)
        if f is not None:
            try:
                f.set(instance, value)
                return True
            except Exception:
                pass
        return False

    def _get_folder_id(self, instance):
        v = self._get_field(instance, "folderId")
        return int(v) if v is not None else 0

    def _should_pin(self, instance):
        mode = self.plugin.get_setting("pin_mode", 0)
        folder_id = self._get_folder_id(instance)
        is_archive = (folder_id == 1)
        if mode == 0 and not is_archive:
            return True
        if mode == 1 and is_archive:
            return True
        if mode == 2:
            return True
        return False

    def _get_dp81(self):
        if self._dp81 is None:
            try:
                from org.telegram.messenger import AndroidUtilities
                self._dp81 = float(int(AndroidUtilities.dp(jfloat(81.0))))
            except Exception:
                self._dp81 = 0.0
        return self._dp81

    def _get_search_dp(self):
        if self._search_dp is None:
            try:
                from org.telegram.messenger import AndroidUtilities
                self._search_dp = int(AndroidUtilities.dp(jfloat(48.0)))
            except Exception:
                self._search_dp = 0
        return self._search_dp

    def _force_collapsed_stories(self, instance):
        was_true = (self._get_field(instance, "hasStories") == True)
        self._set_field(instance, "hasStories", False)
        self._set_field(instance, "animateToHasStories", False)
        if not self._set_field(instance, "hasOnlySlefStories", True):
            self._set_field(instance, "hasOnlySelfStories", True)
        self._set_field(instance, "dialogStoriesCellVisible", True)
        cell = self._get_field(instance, "dialogStoriesCell")
        if cell is not None:
            try:
                cell.setVisibility(0)
            except Exception:
                pass
        if was_true:
            fv = self._get_field(instance, "fragmentView")
            if fv is not None:
                try:
                    fv.requestLayout()
                except Exception:
                    pass

    def _restore_stories(self, instance):
        self._set_field(instance, "hasStories", True)
        self._set_field(instance, "animateToHasStories", True)
        if not self._set_field(instance, "hasOnlySlefStories", False):
            self._set_field(instance, "hasOnlySelfStories", False)

    def trigger_expand(self):
        instance = self._last_instance
        if instance is None:
            return
        self._expanded_by_user = True
        self._expand_time = time.time()
        self._restore_stories(instance)
        try:
            cls = instance.getClass()
            while cls is not None:
                try:
                    m = cls.getDeclaredMethod(
                        "scrollToTop", JBoolean.TYPE, JBoolean.TYPE
                    )
                    m.setAccessible(True)
                    m.invoke(instance, True, True)
                    return
                except Exception:
                    cls = cls.getSuperclass()
        except Exception:
            pass

    def apply_style(self, instance):
        try:
            search_field = self._get_field(instance, "fragmentSearchField")
            if search_field is None:
                return

            bg_hex = self.plugin.get_setting("panel_bg_color", "")
            text_hex = self.plugin.get_setting("panel_text_color", "")
            icon_hex = self.plugin.get_setting("panel_icon_color", "")
            radius_str = self.plugin.get_setting("panel_radius", "")

            bg_color = parse_color(bg_hex)
            text_color = parse_color(text_hex)
            icon_color = parse_color(icon_hex)

            radius = 0.0
            if radius_str:
                try:
                    radius = float(radius_str.strip())
                except Exception:
                    radius = 0.0

            if bg_color is None and text_color is None and icon_color is None and radius <= 0:
                return

            from org.telegram.messenger import AndroidUtilities

            if bg_color is not None or radius > 0:
                try:
                    from android.graphics.drawable import GradientDrawable
                    drawable = GradientDrawable()
                    if bg_color is not None:
                        drawable.setColor(bg_color)
                    if radius > 0:
                        drawable.setCornerRadius(float(AndroidUtilities.dp(jfloat(float(radius)))))
                    search_field.setBackground(drawable)
                except Exception:
                    pass

            edit_text = None
            try:
                edit_text = search_field.editText
            except Exception:
                pass

            if edit_text is not None and text_color is not None:
                try:
                    edit_text.setHintTextColor(text_color)
                except Exception:
                    pass

            effective_icon = icon_color if icon_color is not None else text_color
            if effective_icon is not None:
                try:
                    from android.graphics import PorterDuff, PorterDuffColorFilter
                    si = self._get_field(search_field, "searchIcon")
                    if si is not None:
                        si.setColorFilter(PorterDuffColorFilter(effective_icon, PorterDuff.Mode.SRC_IN))
                except Exception:
                    pass
                try:
                    from android.graphics import PorterDuff, PorterDuffColorFilter
                    ci = self._get_field(search_field, "closeIcon")
                    if ci is not None:
                        ci.setColorFilter(PorterDuffColorFilter(effective_icon, PorterDuff.Mode.SRC_IN))
                except Exception:
                    pass

        except Exception:
            pass

    def before_hooked_method(self, param):
        try:
            value = param.args[0]
            if value is None:
                return

            fval = float(value)
            self._last_instance = param.thisObject

            should_pin = self._should_pin(param.thisObject)
            collapse = self.plugin.get_setting("collapse_stories", False)

            folder_id = self._get_folder_id(param.thisObject)
            is_archive = (folder_id == 1)

            if collapse and not is_archive:
                if self._expanded_by_user:
                    dp81 = self._get_dp81()
                    elapsed = time.time() - self._expand_time
                    if dp81 > 0 and fval <= -dp81 and elapsed > 0.6:
                        self._expanded_by_user = False
                        self._force_collapsed_stories(param.thisObject)
                        self._set_field(
                            param.thisObject,
                            "scrollAdditionalOffset",
                            float(-dp81),
                        )
                        new_val = fval + dp81
                        if should_pin and new_val < 0:
                            new_val = 0.0
                        param.args[0] = JFloat(float(new_val))
                    return
                self._force_collapsed_stories(param.thisObject)

            if should_pin and fval < 0:
                param.args[0] = JFloat(0.0)
        except Exception:
            pass

    def after_hooked_method(self, param):
        if not self._style_applied:
            self._style_applied = True
            try:
                self.apply_style(param.thisObject)
            except Exception:
                self._style_applied = False


class GetMaxScrollYOffsetHook(MethodHook):

    def __init__(self, scroll_y_hook):
        self.syh = scroll_y_hook

    def after_hooked_method(self, param):
        try:
            if not self.syh._should_pin(param.thisObject):
                return
            search_h = self.syh._get_search_dp()
            if search_h <= 0:
                return
            result = param.getResult()
            if result is None:
                return
            current = int(result)
            new_val = current - search_h
            if new_val < 0:
                new_val = 0
            param.setResult(JInteger(new_val))
        except Exception:
            pass


class CheckAutoscrollHook(MethodHook):

    def __init__(self, scroll_y_hook):
        self.syh = scroll_y_hook

    def before_hooked_method(self, param):
        try:
            if not self.syh._should_pin(param.thisObject):
                return
            scroll_y_offset = self.syh._get_field(param.thisObject, "scrollYOffset")
            if scroll_y_offset is None:
                return
            scroll_y = int(-float(scroll_y_offset))
            if scroll_y == 0:
                param.setResult(JBoolean(False))
                return
            has_stories = self.syh._get_field(param.thisObject, "hasStories")
            collapse = self.syh.plugin.get_setting("collapse_stories", False)
            folder_id = self.syh._get_folder_id(param.thisObject)
            is_archive = (folder_id == 1)
            if collapse and not is_archive:
                has_stories = False
            if not has_stories:
                param.setResult(JBoolean(False))
                return
            from org.telegram.messenger import AndroidUtilities
            stories_h = int(AndroidUtilities.dp(jfloat(81.0)))
            if scroll_y == stories_h:
                param.setResult(JBoolean(False))
                return
            view_pages = self.syh._get_field(param.thisObject, "viewPages")
            if view_pages is None:
                return
            page = view_pages[0]
            if page is None:
                return
            list_view = self.syh._get_field(page, "listView")
            if list_view is None:
                return
            can_scroll_up = list_view.canScrollVertically(-1)
            if not can_scroll_up and scroll_y > 0:
                param.setResult(JBoolean(False))
                return
            scroller = self.syh._get_field(page, "scroller")
            if scroller is None:
                return
            dialog_stories_cell = self.syh._get_field(param.thisObject, "dialogStoriesCell")
            k_val = 0.5
            if dialog_stories_cell is not None:
                try:
                    k_field = self.syh._resolve_field(dialog_stories_cell, "K")
                    if k_field is not None:
                        k_val = float(k_field.get(dialog_stories_cell))
                except Exception:
                    pass
            progress = min(1.0, max(0.0, float(scroll_y) / float(stories_h))) if stories_h > 0 else 0.0
            if progress < k_val:
                scroller.smoothScrollBy(-scroll_y)
            else:
                scroller.smoothScrollBy(stories_h - scroll_y)
            param.setResult(JBoolean(True))
        except Exception:
            pass


class ScrollToTopHook(MethodHook):

    def __init__(self, scroll_y_hook):
        self.syh = scroll_y_hook

    def before_hooked_method(self, param):
        try:
            if len(param.args) >= 2 and bool(param.args[1]):
                collapse = self.syh.plugin.get_setting(
                    "collapse_stories", False
                )
                folder_id = self.syh._get_folder_id(param.thisObject)
                if collapse and folder_id != 1 and not self.syh._expanded_by_user:
                    self.syh._expanded_by_user = True
                    self.syh._expand_time = time.time()
                    self.syh._restore_stories(param.thisObject)
        except Exception:
            pass


class OpenSelfStoriesHook(MethodHook):

    def __init__(self, scroll_y_hook):
        self.syh = scroll_y_hook

    def before_hooked_method(self, param):
        try:
            collapse = self.syh.plugin.get_setting(
                "collapse_stories", False
            )
            if not collapse:
                return
            instance = self.syh._last_instance
            if instance is not None:
                folder_id = self.syh._get_folder_id(instance)
                if folder_id == 1:
                    return
            if not self.syh._expanded_by_user:
                param.setResult(None)
                self.syh.trigger_expand()
        except Exception:
            pass



# ============================================================
# MaxExteraPlugins Shared Author & Channel Subscription Module
# ============================================================

# ============================================================
# MaxExteraPlugins Shared Author & Channel Subscription Module
# ============================================================
class AuthorChannelHelper:
    CONFIG_URL = "https://raw.githubusercontent.com/MaxExteraPlugins/config/main/links.json"

    DEFAULT_LINKS = {
        "channel_username": "MaxExteraPlugins",
        "channel_url": "https://t.me/MaxExteraPlugins",
        "trial_days": 7,
        "header": {"ru": "MaxExteraPlugins", "en": "MaxExteraPlugins"},
        "buttons": [
            {"title": {"ru": "Канал автора", "en": "Author's Channel"}, "icon": "msg_channel", "url": "https://t.me/MaxExteraPlugins"},
            {"title": {"ru": "Поддержать автора", "en": "Support author"}, "icon": "msg_share", "url": "https://t.me/itNotMax"},
            {"title": {"ru": "Сообщить о баге", "en": "Report a bug"}, "icon": "msg_help", "url": "https://t.me/itNotMax"}
        ]
    }

    _TEXTS = {
        "install_card_title": {"ru": "Спасибо за установку!", "en": "Thank you for installing!"},
        "install_card_msg": {
            "ru": "Надеемся, что плагин будет вам полезен!\n\nМы делаем плагины бесплатными и доступными для всех: пожалуйста, поддержите нас подпиской. Там будут только важные новости, обновления и розыгрыши.",
            "en": "We hope this plugin will be useful to you!\n\nWe keep our plugins free and open for everyone: please support us with a subscription. We only post key news, updates, and giveaways."
        },
        "subscribe_btn": {"ru": "Подписаться", "en": "Subscribe"},
        "remind_later_btn": {"ru": "Напомнить позже", "en": "Remind later"},
        "check_sub_btn": {"ru": "Проверить подписку", "en": "Check subscription"},
        "trial_expired_title": {"ru": "Пожалуйста, подпишитесь на канал", "en": "Please subscribe to the channel"},
        "trial_expired_msg": {
            "ru": "Пожалуйста, подпишитесь на наш официальный канал.\n\nМы делаем плагины бесплатно, ничего не требуя взамен. До подписки функции плагина временно приостановлены.",
            "en": "Please subscribe to our official channel.\n\nWe develop plugins for free and ask nothing in return. Plugin features are paused until you subscribe."
        },
        "sub_thank_you": {"ru": "Спасибо за подписку на наш канал!", "en": "Thank you for subscribing to our channel!"},
        "sub_thank_you_after_expired": {"ru": "Спасибо за подписку на наш канал!\nПлагин продолжит работу!", "en": "Thank you for subscribing to our channel!\nThe plugin will continue working!"},
        "sub_not_found": {"ru": "Подписка не обнаружена. Пожалуйста, подпишитесь на канал.", "en": "Subscription not found. Please subscribe to the channel."},
        "settings_channel": {"ru": "Канал автора", "en": "Author's Channel"},
        "settings_donate": {"ru": "Поддержать автора", "en": "Support author"},
        "settings_bug_report": {"ru": "Сообщить о баге", "en": "Report a bug"}
    }

    @classmethod
    def is_ru(cls) -> bool:
        try:
            from org.telegram.messenger import LocaleController
            cur = str(LocaleController.getInstance().getCurrentLocale().getLanguage() or "").lower()
            if cur.startswith(("ru", "uk", "be")): return True
            if cur: return False
        except Exception:
            pass
        try:
            from java.util import Locale
            code = str(Locale.getDefault().getLanguage() or "").lower()
            if code.startswith(("ru", "uk", "be")): return True
        except Exception:
            pass
        return False

    @classmethod
    def tr(cls, key: str) -> str:
        entry = cls._TEXTS.get(key, {})
        return entry.get("ru" if cls.is_ru() else "en", entry.get("en", key))

    def __init__(self, plugin, icon_sticker=None):
        self.plugin = plugin
        self.icon_sticker = icon_sticker or getattr(plugin, "__icon__", "MaxExteraPluginsStickers/1")
        self._stopped = False
        self._active_dialog = None
        self._last_known_sub = None

    def on_load(self):
        self._stopped = False
        self._active_dialog = None
        self._last_known_sub = None
        self._load_remote_links_async()
        self._check_initial_subscription_flow()
        self._start_subscription_watcher()

    def on_event(self, event_type):
        try:
            name = str(event_type).upper()
            if name.endswith("START") or name.endswith("RESUME"):
                self._check_subscription_change_instant()
        except Exception:
            pass

    def on_unload(self):
        self._stopped = True
        self._dismiss_active_dialog()

    def _get_links(self) -> dict:
        raw = self.plugin.get_setting("remote_links_cache", None)
        if raw:
            try:
                import json
                data = json.loads(raw)
                if isinstance(data, dict): return data
            except Exception:
                pass
        return self.DEFAULT_LINKS

    def _load_remote_links_async(self):
        def worker():
            try:
                import urllib.request, json
                req = urllib.request.Request(self.CONFIG_URL, headers={"User-Agent": "MaxExteraPlugins"})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        if isinstance(data, dict):
                            self.plugin.set_setting("remote_links_cache", json.dumps(data))
                            self._resolve_channel_in_telegram(data.get("channel_username", "MaxExteraPlugins"))
            except Exception:
                pass
        import threading
        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _open_url(self, url: str, view=None):
        try:
            from org.telegram.messenger.browser import Browser
            from org.telegram.messenger import ApplicationLoader
            from client_utils import get_last_fragment
            ctx = None
            if view is not None:
                ctx = view.getContext()
            if ctx is None:
                frag = get_last_fragment()
                if frag is not None:
                    ctx = frag.getParentActivity()
            if ctx is None:
                ctx = ApplicationLoader.applicationContext
            Browser.openUrl(ctx, url)
        except Exception:
            pass

    def _resolve_channel_in_telegram(self, username: str):
        try:
            from org.telegram.messenger import UserConfig, MessagesController
            from org.telegram.tgnet import TLRPC, ConnectionsManager, RequestDelegate
            clean_user = username.lstrip("@")
            acc = int(UserConfig.selectedAccount)
            mc = MessagesController.getInstance(acc)
            if not mc: return
            req = TLRPC.TL_contacts_resolveUsername()
            req.username = clean_user
            helper_ref = self
            class Delegate(RequestDelegate):
                def run(self, response, error):
                    if error is None and response is not None:
                        chats = getattr(response, "chats", None)
                        if chats is not None and chats.size() > 0:
                            mc.putChats(chats, False)
                            c = chats.get(0)
                            cid = getattr(c, "id", 0)
                            if cid > 0:
                                helper_ref.plugin.set_setting("resolved_channel_id", int(cid))
            ConnectionsManager.getInstance(acc).sendRequest(req, Delegate())
        except Exception:
            pass

    def is_subscribed(self) -> bool:
        try:
            from org.telegram.messenger import UserConfig, MessagesController
            links = self._get_links()
            target = str(links.get("channel_username", "MaxExteraPlugins") or "MaxExteraPlugins").lower().lstrip("@")
            saved_cid = self.plugin.get_setting("resolved_channel_id", 0)

            for acc in range(UserConfig.MAX_ACCOUNT_COUNT):
                uconf = UserConfig.getInstance(acc)
                if not uconf.isClientActivated(): continue
                mc = MessagesController.getInstance(acc)
                if not mc: continue

                if saved_cid:
                    try:
                        from java.lang import Long as JLong
                        c = mc.getChat(JLong(int(saved_cid)))
                        if c is not None:
                            left = bool(getattr(c, "left", True))
                            kicked = bool(getattr(c, "kicked", False))
                            if not left and not kicked: return True
                    except Exception:
                        pass

                try:
                    chat = mc.getUserOrChat(target)
                    if chat is not None:
                        cid = getattr(chat, "id", 0)
                        if cid and not saved_cid:
                            self.plugin.set_setting("resolved_channel_id", int(cid))
                        left = bool(getattr(chat, "left", True))
                        kicked = bool(getattr(chat, "kicked", False))
                        if not left and not kicked: return True
                except Exception:
                    pass

                try:
                    dialogs = mc.allDialogs
                    if dialogs is not None:
                        limit = min(dialogs.size(), 300)
                        for i in range(limit):
                            d = dialogs.get(i)
                            did = getattr(d, "id", 0)
                            if did < 0:
                                from java.lang import Long as JLong
                                c = mc.getChat(JLong(-did))
                                if c is not None:
                                    uname = str(getattr(c, "username", "") or "").lower()
                                    if uname == target:
                                        cid = getattr(c, "id", 0)
                                        if cid and not saved_cid:
                                            self.plugin.set_setting("resolved_channel_id", int(cid))
                                        left = bool(getattr(c, "left", True))
                                        kicked = bool(getattr(c, "kicked", False))
                                        if not left and not kicked: return True
                except Exception:
                    pass
        except Exception:
            pass
        return False

    def is_allowed(self) -> bool:
        import time
        if self.is_subscribed():
            if not self.plugin.get_setting("was_subscribed", False):
                was_exp = bool(self.plugin.get_setting("was_expired_state", False))
                self.plugin.set_setting("was_subscribed", True)
                self.plugin.set_setting("was_expired_state", False)
                self._notify_subscribed(was_expired=was_exp)
            return True

        if self.plugin.get_setting("was_expired_state", False) or self.plugin.get_setting("was_subscribed", False):
            self.plugin.set_setting("was_subscribed", False)
            self.plugin.set_setting("was_expired_state", True)
            self._show_expired_card()
            return False

        now = time.time()
        install_time = float(self.plugin.get_setting("install_time", 0.0) or 0.0)
        if install_time <= 0:
            install_time = now
            self.plugin.set_setting("install_time", install_time)

        trial_days = float(self._get_links().get("trial_days", 7))
        trial_sec = trial_days * 86400.0

        if (now - install_time) < trial_sec:
            return True

        self.plugin.set_setting("was_expired_state", True)
        self._show_expired_card()
        return False

    def prepend_settings(self, original_items=None) -> list:
        from ui.settings import Header, Text, Divider

        # Prevent double-prepending
        if original_items and any(getattr(x, "text", "") == "MaxExteraPlugins" for x in original_items if type(x).__name__ == "Header"):
            return original_items

        links = self._get_links()
        buttons_config = links.get("buttons")

        author_items = []
        if isinstance(buttons_config, list):
            for btn in buttons_config:
                if not isinstance(btn, dict): continue
                url = str(btn.get("url") or "").strip()
                if not url: continue

                title_data = btn.get("title")
                if isinstance(title_data, dict):
                    title = title_data.get("ru" if self.is_ru() else "en") or title_data.get("en") or title_data.get("ru") or ""
                elif isinstance(title_data, str) and title_data:
                    title = title_data
                else:
                    title = btn.get("title_ru" if self.is_ru() else "title_en") or btn.get("title_ru") or btn.get("title_en") or ""

                if not title: continue
                icon = str(btn.get("icon") or "msg_channel").strip()

                def make_click(u):
                    return lambda v=None: self._open_url(u, v)

                author_items.append(Text(text=title, icon=icon, on_click=make_click(url)))
        else:
            for k, text_key, icon_name in [
                ("channel_url", "settings_channel", "msg_channel"),
                ("donate_url", "settings_donate", "msg_share"),
                ("bug_report_url", "settings_bug_report", "msg_help")
            ]:
                u = str(links.get(k) or "").strip()
                if u:
                    author_items.append(Text(text=self.tr(text_key), icon=icon_name, on_click=lambda v=None, target_u=u: self._open_url(target_u, v)))

        res = []
        if author_items:
            hdr = links.get("header") or "MaxExteraPlugins"
            if isinstance(hdr, dict):
                hdr_text = hdr.get("ru" if self.is_ru() else "en") or hdr.get("ru") or hdr.get("en") or "MaxExteraPlugins"
            else:
                hdr_text = str(hdr)
            res.append(Header(text=hdr_text))
            res.extend(author_items)
            res.append(Divider())

        # Clean original_items by removing any old "Информация" / "Information" category
        cleaned_items = []
        if original_items:
            skipping_info = False
            for item in original_items:
                item_cls = type(item).__name__
                if item_cls == "Header":
                    txt = str(getattr(item, "text", "") or getattr(item, "title", "") or "").lower()
                    if "информ" in txt or "inform" in txt:
                        skipping_info = True
                        continue
                    else:
                        skipping_info = False
                elif skipping_info and item_cls == "Divider":
                    skipping_info = False
                    continue

                if not skipping_info:
                    cleaned_items.append(item)

        res.extend(cleaned_items)
        return res

    def _dismiss_active_dialog(self):
        try:
            if self._active_dialog is not None:
                self._active_dialog.dismiss()
        except Exception:
            pass
        self._active_dialog = None

    def _is_dialog_active(self) -> bool:
        try:
            if self._active_dialog is not None:
                return bool(self._active_dialog.isShowing())
        except Exception:
            pass
        return False

    def _notify_subscribed(self, was_expired=False):
        self.plugin.set_setting("was_subscribed", True)
        from ui.bulletin import BulletinHelper
        msg_key = "sub_thank_you_after_expired" if was_expired else "sub_thank_you"
        BulletinHelper.show_success(self.tr(msg_key))

    def _check_subscription_change_instant(self):
        try:
            from android_utils import run_on_ui_thread
            cur_sub = self.is_subscribed()
            prev_sub = self._last_known_sub
            if prev_sub is not None and prev_sub != cur_sub:
                self._last_known_sub = cur_sub
                if cur_sub:
                    was_exp = bool(self.plugin.get_setting("was_expired_state", False))
                    self.plugin.set_setting("was_subscribed", True)
                    self.plugin.set_setting("was_expired_state", False)
                    self._dismiss_active_dialog()
                    self._notify_subscribed(was_expired=was_exp)
                else:
                    self.plugin.set_setting("was_subscribed", False)
                    self.plugin.set_setting("was_expired_state", True)
                    self._dismiss_active_dialog()
                    self._show_expired_card()
            else:
                self._last_known_sub = cur_sub
        except Exception:
            pass

    def _start_subscription_watcher(self):
        def watcher_loop():
            import time
            from android_utils import run_on_ui_thread
            time.sleep(2.0)
            if self._stopped: return
            self._last_known_sub = self.is_subscribed()

            while not self._stopped:
                try:
                    time.sleep(2.0)
                    if self._stopped: break
                    cur_sub = self.is_subscribed()
                    prev_sub = self._last_known_sub

                    if prev_sub is not None and prev_sub != cur_sub:
                        self._last_known_sub = cur_sub
                        if cur_sub:
                            was_exp = bool(self.plugin.get_setting("was_expired_state", False))
                            self.plugin.set_setting("was_subscribed", True)
                            self.plugin.set_setting("was_expired_state", False)
                            def on_sub():
                                self._dismiss_active_dialog()
                                self._notify_subscribed(was_expired=was_exp)
                            run_on_ui_thread(on_sub)
                        else:
                            self.plugin.set_setting("was_subscribed", False)
                            self.plugin.set_setting("was_expired_state", True)
                            def on_unsub():
                                self._dismiss_active_dialog()
                                self._show_expired_card()
                            run_on_ui_thread(on_unsub)
                    else:
                        self._last_known_sub = cur_sub
                except Exception:
                    pass
        import threading
        t = threading.Thread(target=watcher_loop, daemon=True)
        t.start()

    def _check_initial_subscription_flow(self):
        def flow():
            import time
            try:
                now = time.time()
                install_time = float(self.plugin.get_setting("install_time", 0.0) or 0.0)
                if install_time <= 0:
                    install_time = now
                    self.plugin.set_setting("install_time", install_time)

                is_sub = self.is_subscribed()
                self._last_known_sub = is_sub
                was_sub = bool(self.plugin.get_setting("was_subscribed", False))
                was_exp = bool(self.plugin.get_setting("was_expired_state", False))

                if is_sub:
                    if not was_sub:
                        self.plugin.set_setting("was_subscribed", True)
                        self.plugin.set_setting("was_expired_state", False)
                        self._notify_subscribed(was_expired=was_exp)
                    return

                if was_sub or was_exp:
                    self.plugin.set_setting("was_subscribed", False)
                    self.plugin.set_setting("was_expired_state", True)
                    self._show_expired_card()
                    return

                trial_days = float(self._get_links().get("trial_days", 7))
                trial_sec = trial_days * 86400.0
                last_remind = float(self.plugin.get_setting("last_remind_time", 0.0) or 0.0)

                if (now - install_time) < trial_sec:
                    if last_remind <= 0 or (now - last_remind) >= trial_sec:
                        self._show_welcome_card()
                else:
                    self.plugin.set_setting("was_expired_state", True)
                    self._show_expired_card()
            except Exception:
                pass
        from android_utils import run_on_ui_thread
        run_on_ui_thread(flow, 1500)

    def _create_card_content(self, act, title_text, message_text):
        try:
            from android.widget import LinearLayout, TextView
            from android.view import Gravity
            from android.graphics import Typeface
            from org.telegram.messenger import AndroidUtilities, UserConfig, MediaDataController
            from org.telegram.ui.ActionBar import Theme
            from org.telegram.ui.Components import BackupImageView

            dp = AndroidUtilities.dp
            layout = LinearLayout(act)
            layout.setOrientation(LinearLayout.VERTICAL)
            layout.setGravity(Gravity.CENTER_HORIZONTAL)
            layout.setPadding(dp(24), dp(16), dp(24), dp(6))

            size = dp(76)
            iv = BackupImageView(act)
            iv.setRoundRadius(dp(18))
            lp_iv = LinearLayout.LayoutParams(size, size)
            lp_iv.gravity = Gravity.CENTER_HORIZONTAL
            lp_iv.setMargins(0, dp(4), 0, dp(16))
            iv.setLayoutParams(lp_iv)

            try:
                acc = int(UserConfig.selectedAccount)
                mdc = MediaDataController.getInstance(acc)
                raw_icon = str(self.icon_sticker)
                if "/" in raw_icon:
                    pack, idx_s = raw_icon.split("/", 1)
                    mdc.setPlaceholderImageByIndex(iv, pack, int(idx_s), "150_150")
            except Exception:
                pass
            layout.addView(iv)

            if title_text:
                tt = TextView(act)
                tt.setText(title_text)
                tt.setTextSize(19.0)
                tt.setTypeface(None, Typeface.BOLD)
                tt.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
                tt.setGravity(Gravity.CENTER_HORIZONTAL)
                lp_t = LinearLayout.LayoutParams(-1, -2)
                lp_t.setMargins(0, 0, 0, dp(12))
                tt.setLayoutParams(lp_t)
                layout.addView(tt)

            if message_text:
                mt = TextView(act)
                mt.setText(message_text)
                mt.setTextSize(15.0)
                mt.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
                mt.setLineSpacing(float(dp(3)), 1.0)
                mt.setGravity(Gravity.CENTER_HORIZONTAL)
                lp_m = LinearLayout.LayoutParams(-1, -2)
                mt.setLayoutParams(lp_m)
                layout.addView(mt)

            return layout
        except Exception:
            return None

    def _show_welcome_card(self):
        def show():
            try:
                if self._is_dialog_active(): return
                from client_utils import get_last_fragment
                frag = get_last_fragment()
                if not frag: return
                act = frag.getParentActivity()
                if not act: return

                links = self._get_links()
                url = links.get("channel_url", "https://t.me/MaxExteraPlugins")

                from ui.alert import AlertDialogBuilder
                b = AlertDialogBuilder(act)
                content = self._create_card_content(act, self.tr("install_card_title"), self.tr("install_card_msg"))
                if content is not None:
                    b.set_view(content)
                else:
                    b.set_title(self.tr("install_card_title"))
                    b.set_message(self.tr("install_card_msg"))

                def on_sub(d, w):
                    self._dismiss_active_dialog()
                    self._open_url(url)
                    def check_after():
                        if self.is_subscribed():
                            self._notify_subscribed(was_expired=False)
                    from android_utils import run_on_ui_thread
                    run_on_ui_thread(check_after, 3000)

                def on_later(d, w):
                    import time
                    self._dismiss_active_dialog()
                    self.plugin.set_setting("last_remind_time", time.time())

                b.set_positive_button(self.tr("subscribe_btn"), on_sub)
                b.set_negative_button(self.tr("remind_later_btn"), on_later)
                self._active_dialog = b.show()
            except Exception:
                pass
        from android_utils import run_on_ui_thread
        run_on_ui_thread(show)

    def _show_expired_card(self):
        def show():
            try:
                if self._is_dialog_active(): return
                from client_utils import get_last_fragment
                frag = get_last_fragment()
                if not frag: return
                act = frag.getParentActivity()
                if not act: return

                links = self._get_links()
                url = links.get("channel_url", "https://t.me/MaxExteraPlugins")

                from ui.alert import AlertDialogBuilder
                from ui.bulletin import BulletinHelper
                b = AlertDialogBuilder(act)
                content = self._create_card_content(act, self.tr("trial_expired_title"), self.tr("trial_expired_msg"))
                if content is not None:
                    b.set_view(content)
                else:
                    b.set_title(self.tr("trial_expired_title"))
                    b.set_message(self.tr("trial_expired_msg"))

                def on_sub(d, w):
                    self._dismiss_active_dialog()
                    self._open_url(url)
                    def check_after():
                        if self.is_subscribed():
                            self.plugin.set_setting("was_subscribed", True)
                            self.plugin.set_setting("was_expired_state", False)
                            self._notify_subscribed(was_expired=True)
                    from android_utils import run_on_ui_thread
                    run_on_ui_thread(check_after, 3000)

                def on_check(d, w):
                    self._dismiss_active_dialog()
                    if self.is_subscribed():
                        self.plugin.set_setting("was_subscribed", True)
                        self.plugin.set_setting("was_expired_state", False)
                        self._notify_subscribed(was_expired=True)
                    else:
                        BulletinHelper.show_error(self.tr("sub_not_found"))
                        from android_utils import run_on_ui_thread
                        run_on_ui_thread(self._show_expired_card, 500)

                b.set_positive_button(self.tr("subscribe_btn"), on_sub)
                b.set_negative_button(self.tr("check_sub_btn"), on_check)
                self._active_dialog = b.show()
            except Exception:
                pass
        from android_utils import run_on_ui_thread
        run_on_ui_thread(show)


class SearchBarControlPlugin(BasePlugin):
    def on_app_event(self, event_type):
        if hasattr(self, "_author_helper"):
            self._author_helper.on_event(event_type)

    def on_plugin_load(self):
        self._author_helper = AuthorChannelHelper(self, icon_sticker="MaxExteraPluginsStickers/3")
        self._author_helper.on_load()
        cls = find_class("org.telegram.ui.DialogsActivity")
        if not cls:
            return

        scroll_hook = ScrollYHook(self)
        self._scroll_hook = scroll_hook

        try:
            self.hook_all_methods(cls, "setScrollY", scroll_hook)
        except Exception:
            pass

        try:
            self.hook_all_methods(cls, "getMaxScrollYOffset", GetMaxScrollYOffsetHook(scroll_hook))
        except Exception:
            pass

        try:
            self.hook_all_methods(cls, "checkAutoscrollToStories", CheckAutoscrollHook(scroll_hook))
        except Exception:
            pass

        try:
            self.hook_all_methods(
                cls, "scrollToTop", ScrollToTopHook(scroll_hook)
            )
        except Exception:
            pass

        stories_cls = find_class(
            "org.telegram.ui.Stories.DialogStoriesCell"
        )
        if stories_cls:
            try:
                self.hook_all_methods(
                    stories_cls,
                    "openSelfStories",
                    OpenSelfStoriesHook(scroll_hook),
                )
            except Exception:
                pass

    def _open_internal(self, url):
        def handler(view):
            try:
                from org.telegram.messenger.browser import Browser
                ctx = view.getContext()
                Browser.openAsInternalIntent(ctx, url)
            except Exception:
                pass
        return handler

    def _open_telegraph(self, url):
        def handler(view):
            try:
                from android.net import Uri
                from org.telegram.messenger.browser import Browser
                ctx = view.getContext()
                Browser.openUrl(ctx, Uri.parse(url), True, True)
            except Exception:
                pass
        return handler

    def _on_style_change(self, new_value):
        try:
            hook = getattr(self, "_scroll_hook", None)
            if hook is not None and hook._last_instance is not None:
                hook._style_applied = False
                from org.telegram.messenger import AndroidUtilities
                AndroidUtilities.runOnUIThread(lambda: hook.apply_style(hook._last_instance))
        except Exception:
            pass

    def _on_lang_change(self, new_value):
        try:
            if hasattr(self, "reload_settings"):
                self.reload_settings()
            elif hasattr(self, "update_settings"):
                self.update_settings()
            elif hasattr(self, "refresh_settings"):
                self.refresh_settings()
        except Exception:
            pass

    def create_settings(self):
        try:
            items = self._inner_create_settings()
        except Exception:
            items = []
        if hasattr(self, '_author_helper'):
            return self._author_helper.prepend_settings(items)
        return items

    def _inner_create_settings(self):
        lang = self.get_setting("lang", 0)
        is_ru = (lang == 1)
        return [
            Header(text="Localization" if not is_ru else "Локализация"),
            Selector(
                key="lang",
                text="Language" if not is_ru else "Язык",
                default=0,
                items=["English", "Русский"],
                on_change=self._on_lang_change,
            ),
            Divider(),
            Header(text="Information" if not is_ru else "Информация"),
            Text(
                text="Documentation" if not is_ru else "Документация",
                icon="msg_link",
                on_click=self._open_telegraph("https://telegra.ph/Dokumentaciya-k-plaginu-Search-Bar-Control-06-28"),
            ),
            Text(
                text="Author Channel" if not is_ru else "Канал автора",
                icon="msg_channel",
                on_click=self._open_internal("https://t.me/MaxExteraPlugins"),
            ),
            Divider(),
            Header(text="Search Bar" if not is_ru else "Строка поиска"),
            Text(
                text="Hide Search Bar" if not is_ru else "Скрыть строку поиска",
                icon="msg_customize",
                subtext="Open exteraGram settings" if not is_ru else "Открыть настройки exteraGram",
                on_click=self._open_internal("https://t.me/exteraSettings?s=hideDialogsSearchBar"),
            ),
            Selector(
                key="pin_mode",
                text="Pin Mode:" if not is_ru else "Закреплять:",
                default=0,
                items=[
                    "Main page only",
                    "Archive only",
                    "Everywhere (Main + Archive)",
                ] if not is_ru else [
                    "Только на главной",
                    "Только в архиве",
                    "Везде (главная+архив)",
                ],
            ),
            Divider(),
            Header(text="Stories" if not is_ru else "Истории"),
            Text(
                text="Hide Stories" if not is_ru else "Скрыть истории",
                icon="msg_customize",
                subtext="Open exteraGram settings" if not is_ru else "Открыть настройки exteraGram",
                on_click=self._open_internal("https://t.me/exteraSettings?s=hideStories"),
            ),
            Switch(
                key="collapse_stories",
                text="Collapse Stories" if not is_ru else "Свернуть истории",
                default=False,
            ),
            Divider(),
            Header(text="Panel Customization" if not is_ru else "Кастомизация панели"),
            Input(
                key="panel_bg_color",
                text="Background Color" if not is_ru else "Цвет фона",
                default="",
                subtext="#RRGGBB or #RRGGBBAA" if not is_ru else "#RRGGBB или #RRGGBBAA",
                on_change=self._on_style_change,
            ),
            Input(
                key="panel_text_color",
                text="Hint Text Color" if not is_ru else "Цвет подсказки",
                default="",
                subtext="#RRGGBB or #RRGGBBAA — label «Search chats»" if not is_ru else "#RRGGBB или #RRGGBBAA — надпись «Поиск чатов»",
                on_change=self._on_style_change,
            ),
            Input(
                key="panel_icon_color",
                text="Icon Color" if not is_ru else "Цвет иконок",
                default="",
                subtext="#RRGGBB or #RRGGBBAA (empty = text color)" if not is_ru else "#RRGGBB или #RRGGBBAA (если пусто = цвет текста)",
                on_change=self._on_style_change,
            ),
            Input(
                key="panel_radius",
                text="Corner Radius (dp)" if not is_ru else "Закругление углов (dp)",
                default="",
                subtext="Number, e.g.: 18" if not is_ru else "Число, например: 18",
                on_change=self._on_style_change,
            ),
        ]

    def on_plugin_unload(self):
        if hasattr(self, "_author_helper"):
            self._author_helper.on_unload()
        pass
