import os
import json
import threading
import sys
import math
import struct
import urllib.request
from datetime import datetime
import pygame
from openai import OpenAI

# ---------------------------------------------------------
# 1. PATHS & INITIALIZATION
# ---------------------------------------------------------
LM_STUDIO_URL = "http://localhost:1234/v1"
SAVES_DIR = "saves"
PERSONAS_DIR = "personas"
USER_PERSONAS_DIR = "user_personas"
EXPORTS_DIR = "exports"
SFX_DIR = "sfx"
LORE_FILE = "lore.txt"

FONT_SIZE = 17
LINE_SPACING = 23
MAX_CONTEXT_MESSAGES = 16

os.makedirs(SAVES_DIR, exist_ok=True)
os.makedirs(PERSONAS_DIR, exist_ok=True)
os.makedirs(USER_PERSONAS_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)
os.makedirs(SFX_DIR, exist_ok=True)

pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)

pygame.display.set_caption("PyChat window - 1.0 beta")
screen = pygame.display.set_mode((1100, 760), pygame.RESIZABLE)
clock = pygame.time.Clock()

client = OpenAI(base_url=LM_STUDIO_URL, api_key="lm-studio")

# Cyberpunk / Retro-Terminal Color Palette
BG_COLOR = (15, 17, 22)
PANEL_BG = (24, 27, 35)
SIDEBAR_BG = (19, 21, 28)
TEXT_COLOR = (220, 225, 235)
USER_COLOR = (120, 180, 255)
SYSTEM_COLOR = (140, 150, 170)
BORDER_COLOR = (50, 58, 72)
INPUT_BG = (20, 23, 30)
MODAL_BG = (16, 18, 24)

try:
    font = pygame.font.SysFont("Consolas", FONT_SIZE)
    bold_font = pygame.font.SysFont("Consolas", FONT_SIZE, bold=True)
    small_font = pygame.font.SysFont("Consolas", FONT_SIZE - 3)
except Exception:
    font = pygame.font.Font(None, FONT_SIZE)
    bold_font = font
    small_font = font


# ---------------------------------------------------------
# 2. DYNAMIC LORE MANAGEMENT
# ---------------------------------------------------------
def load_world_lore():
    """Loads global universe lore to inject into system prompt context."""
    if not os.path.exists(LORE_FILE):
        default_lore = "GLOBAL UNIVERSE LORE:\n- Terminal operating under an isolated local neural network node."
        with open(LORE_FILE, "w", encoding="utf-8") as f:
            f.write(default_lore)
        return default_lore

    try:
        with open(LORE_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


# ---------------------------------------------------------
# 3. PROCEDURAL AUDIO SYNTHESIZER
# ---------------------------------------------------------
def create_synth_sound(freq_start, freq_end=None, duration_ms=60, volume=0.12, wave_type="sine"):
    sample_rate = 44100
    n_samples = int(sample_rate * (duration_ms / 1000.0))
    buf = bytearray()

    for i in range(n_samples):
        t = float(i) / sample_rate
        progress = i / float(n_samples)
        current_freq = freq_start if freq_end is None else freq_start + (freq_end - freq_start) * progress

        if wave_type == "square":
            val = 0.8 if math.sin(2.0 * math.pi * current_freq * t) >= 0 else -0.8
        elif wave_type == "saw":
            val = 2.0 * (t * current_freq - math.floor(0.5 + t * current_freq))
        else:
            val = math.sin(2.0 * math.pi * current_freq * t)

        envelope = (1.0 - progress) ** 2
        scaled = int(val * volume * envelope * 32767)
        buf.extend(struct.pack("<h", max(-32768, min(32767, scaled))))

    return pygame.mixer.Sound(buffer=bytes(buf))


def create_bootup_sound():
    sample_rate = 44100
    duration_ms = 400
    n_samples = int(sample_rate * (duration_ms / 1000.0))
    buf = bytearray()

    for i in range(n_samples):
        t = float(i) / sample_rate
        progress = i / float(n_samples)
        freq = 220 if progress < 0.3 else (440 if progress < 0.65 else 880)
        val = math.sin(2.0 * math.pi * freq * t) + 0.3 * (
            0.8 if math.sin(2.0 * math.pi * (freq * 2) * t) >= 0 else -0.8)
        envelope = min(1.0, progress * 10) * (1.0 - progress)
        scaled = int(val * 0.15 * envelope * 32767)
        buf.extend(struct.pack("<h", max(-32768, min(32767, scaled))))

    return pygame.mixer.Sound(buffer=bytes(buf))


def load_sfx(filename, synth_fallback):
    filepath = os.path.join(SFX_DIR, filename)
    if os.path.exists(filepath):
        try:
            return pygame.mixer.Sound(filepath)
        except Exception:
            pass
    return synth_fallback


sfx_click = load_sfx("click.wav", create_synth_sound(880, 1200, duration_ms=45, volume=0.08, wave_type="sine"))
sfx_send = load_sfx("send.wav", create_synth_sound(440, 880, duration_ms=80, volume=0.1, wave_type="square"))
sfx_receive = load_sfx("receive.wav", create_synth_sound(600, 1000, duration_ms=120, volume=0.12, wave_type="sine"))
sfx_key = load_sfx("type.wav", create_synth_sound(300, 200, duration_ms=18, volume=0.03, wave_type="saw"))
sfx_boot = load_sfx("boot.wav", create_bootup_sound())


# ---------------------------------------------------------
# 4. CRT SCANLINES & TERMINAL UI DECORATORS
# ---------------------------------------------------------
def draw_crt_scanlines(surface, line_spacing=3, alpha=20):
    scanline_surf = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    for y in range(0, surface.get_height(), line_spacing):
        pygame.draw.line(scanline_surf, (0, 0, 0, alpha), (0, y), (surface.get_width(), y), 1)
    surface.blit(scanline_surf, (0, 0))


def draw_glow_circle(surface, color, center, radius):
    glow_surf = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
    r, g, b = color[:3]
    pygame.draw.circle(glow_surf, (r, g, b, 40), (radius * 2, radius * 2), radius * 2)
    pygame.draw.circle(glow_surf, (r, g, b, 90), (radius * 2, radius * 2), int(radius * 1.4))
    pygame.draw.circle(glow_surf, (r, g, b, 255), (radius * 2, radius * 2), radius)
    surface.blit(glow_surf, (center[0] - radius * 2, center[1] - radius * 2))


def draw_terminal_panel(surface, rect, border_color, fill_color=PANEL_BG):
    pygame.draw.rect(surface, fill_color, rect, border_radius=4)
    pygame.draw.rect(surface, border_color, rect, width=1, border_radius=4)

    c_len = 10
    pygame.draw.line(surface, border_color, (rect.x, rect.y), (rect.x + c_len, rect.y), 2)
    pygame.draw.line(surface, border_color, (rect.x, rect.y), (rect.x, rect.y + c_len), 2)
    pygame.draw.line(surface, border_color, (rect.right - 1, rect.bottom - 1),
                     (rect.right - c_len - 1, rect.bottom - 1), 2)
    pygame.draw.line(surface, border_color, (rect.right - 1, rect.bottom - 1),
                     (rect.right - 1, rect.bottom - c_len - 1), 2)


# ---------------------------------------------------------
# 5. CONNECTION MONITOR THREAD
# ---------------------------------------------------------
lm_studio_online = False


def connection_monitor_thread():
    global lm_studio_online
    while True:
        try:
            req = urllib.request.Request(f"{LM_STUDIO_URL}/models", headers={"User-Agent": "NexusTerminal"})
            with urllib.request.urlopen(req, timeout=1.5) as response:
                lm_studio_online = (response.status == 200)
        except Exception:
            lm_studio_online = False
        pygame.time.wait(3000)


threading.Thread(target=connection_monitor_thread, daemon=True).start()


# ---------------------------------------------------------
# 6. PERSONAS & CUSTOM .CHAT PACKAGE HANDLING
# ---------------------------------------------------------
def load_all_user_personas():
    u_personas = {}
    if os.path.exists(USER_PERSONAS_DIR):
        for fname in os.listdir(USER_PERSONAS_DIR):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(USER_PERSONAS_DIR, fname), "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if "id" in data:
                            if isinstance(data.get("color"), list):
                                data["color"] = tuple(data["color"])
                            u_personas[data["id"]] = data
                except Exception:
                    pass
    return u_personas


def load_all_ai_personas():
    ai_p = {}
    if os.path.exists(PERSONAS_DIR):
        for fname in os.listdir(PERSONAS_DIR):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(PERSONAS_DIR, fname), "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if "id" in data:
                            if isinstance(data.get("color"), list):
                                data["color"] = tuple(data["color"])
                            ai_p[data["id"]] = data
                except Exception:
                    pass
    return ai_p


def export_persona_as_chat_package(ai_id):
    """Exports an AI character, relationship state, and lore to a portable .chat file."""
    ai_personas = load_all_ai_personas()
    if ai_id not in ai_personas: return None

    ai_data = ai_personas[ai_id]
    trust_val = load_relationship(ai_id)
    world_lore = load_world_lore()

    package = {
        "format": "nexus_chat_package",
        "version": "1.0",
        "persona": ai_data,
        "initial_trust": trust_val,
        "bundled_lore": world_lore
    }

    export_path = os.path.join(EXPORTS_DIR, f"{ai_id}.chat")
    with open(export_path, "w", encoding="utf-8") as f:
        json.dump(package, f, indent=2, ensure_ascii=False)

    return export_path


def import_chat_package(filepath):
    """Imports a .chat file package into local personas, relationship files, and lore."""
    if not os.path.exists(filepath) or not filepath.endswith(".chat"):
        return False, "Invalid file format."

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("format") != "nexus_chat_package": return False, "Invalid package format."

        persona = data["persona"]
        p_id = persona["id"]

        with open(os.path.join(PERSONAS_DIR, f"{p_id}.json"), "w", encoding="utf-8") as f:
            json.dump(persona, f, indent=2, ensure_ascii=False)

        if "initial_trust" in data: save_relationship(p_id, data["initial_trust"])

        if data.get("bundled_lore"):
            current_lore = load_world_lore()
            if data["bundled_lore"] not in current_lore:
                with open(LORE_FILE, "a", encoding="utf-8") as f:
                    f.write("\n\n" + data["bundled_lore"])

        return True, p_id
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------
# 7. RELATIONSHIP METRICS
# ---------------------------------------------------------
def get_relationship_path(ai_id):
    return os.path.join(SAVES_DIR, f"rel_{ai_id}.json")


def load_relationship(ai_id):
    path = get_relationship_path(ai_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f).get("trust", 50)
        except Exception:
            pass
    return 50


def save_relationship(ai_id, trust_val):
    with open(get_relationship_path(ai_id), "w", encoding="utf-8") as f:
        json.dump({"trust": trust_val}, f)


def get_relationship_rank(trust):
    if trust >= 85:
        return "UNSHAKEABLE BOND", (100, 255, 180)
    elif trust >= 65:
        return "TRUSTED ALLY", (120, 220, 255)
    elif trust >= 45:
        return "NEUTRAL SYNERGY", (220, 220, 140)
    elif trust >= 25:
        return "CAUTIOUS / DISTRUSTFUL", (255, 170, 80)
    else:
        return "HOSTILE / THREAT", (255, 80, 80)


def calculate_trust_delta(user_text, ai_reply):
    delta = 0
    user_lower = user_text.lower()

    pos_words = ["thank", "thanks", "friend", "help", "cool", "awesome", "trust", "sorry", "nice", "love", "good"]
    neg_words = ["hate", "stupid", "useless", "shut up", "kill", "die", "attack", "worst", "threat", "ugly"]

    for word in pos_words:
        if word in user_lower: delta += 2
    for word in neg_words:
        if word in user_lower: delta -= 5

    if delta == 0: delta = 1
    return delta


# ---------------------------------------------------------
# 8. CHAT ENGINE & SYSTEM PROMPT BUILDER
# ---------------------------------------------------------
def build_combined_system_prompt(ai_id, user_id):
    ai = ai_personas[ai_id]
    u = user_personas[user_id]
    rank_title, _ = get_relationship_rank(current_trust)
    world_lore = load_world_lore()

    return f"""[SYSTEM DIRECTIVE: ROLEPLAY ENFORCEMENT]
{ai.get('base_prompt', ai.get('system_prompt', ''))}

[GLOBAL WORLD LORE]:
{world_lore}

[RELATIONSHIP METRIC]:
Current Trust Level with user: {current_trust}% ({rank_title}).
Dynamically adjust tone, warmth, or hostility based on this percentage.

[INTERACTOR PROFILE]:
User Identity: {u['name']} ({u['species']}, {u['optic_color']} Identifier).
User Lore: {u['lore']}"""


def get_save_path(ai_id):
    return os.path.join(SAVES_DIR, f"chat_history_{ai_id}.json")


def save_chat_history(ai_id, msgs):
    with open(get_save_path(ai_id), "w", encoding="utf-8") as f:
        json.dump(msgs, f, indent=2, ensure_ascii=False)


def load_chat_history(ai_id, user_id):
    spath = get_save_path(ai_id)
    sys_prompt = build_combined_system_prompt(ai_id, user_id)
    if os.path.exists(spath):
        try:
            with open(spath, "r", encoding="utf-8") as f:
                msgs = json.load(f)
                msgs[0] = {"role": "system", "content": sys_prompt}
                return msgs
        except Exception:
            pass
    return [
        {"role": "system", "content": sys_prompt},
        {"role": "assistant", "content": ai_personas[ai_id].get("greeting", "*nods in greeting*")}
    ]


def wrap_text(text, font_obj, max_width):
    lines = []
    for paragraph in text.split('\n'):
        words = paragraph.split(' ')
        if not words or words == ['']:
            lines.append('')
            continue
        current_line = words[0]
        for word in words[1:]:
            test_line = current_line + " " + word
            if font_obj.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)
    return lines


def get_trimmed_messages(messages, max_history=MAX_CONTEXT_MESSAGES):
    if len(messages) <= max_history + 1: return messages
    return [messages[0]] + messages[-max_history:]


def reset_active_chat(ai_id, user_id):
    save_path = get_save_path(ai_id)
    if os.path.exists(save_path):
        try:
            os.remove(save_path)
        except Exception:
            pass

    rel_path = get_relationship_path(ai_id)
    if os.path.exists(rel_path):
        try:
            os.remove(rel_path)
        except Exception:
            pass

    sys_prompt = build_combined_system_prompt(ai_id, user_id)
    return [
        {"role": "system", "content": sys_prompt},
        {"role": "assistant", "content": ai_personas[ai_id].get("greeting", "*nods*")}
    ]


# ---------------------------------------------------------
# 9. FIRST-TIME SETUP WIZARD SCREEN
# ---------------------------------------------------------
def run_first_time_setup():
    step = 1
    fields = {
        "user_name": "", "user_species": "", "user_color": "Cyan",
        "ai_name": "", "ai_subtitle": "", "ai_greeting": "", "ai_prompt": ""
    }
    active_field = "user_name"

    while True:
        clock.tick(60)
        w, h = screen.get_size()
        screen.fill(BG_COLOR)

        frame = pygame.Rect(80, 50, w - 160, h - 100)
        draw_terminal_panel(screen, frame, (0, 220, 255))

        title = bold_font.render(f"FIRST TIME SETUP - STEP {step} OF 2", True, (0, 220, 255))
        screen.blit(title, (frame.x + 30, frame.y + 25))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_BACKSPACE:
                    sfx_key.play()
                    fields[active_field] = fields[active_field][:-1]
                elif event.key == pygame.K_TAB:
                    sfx_click.play()
                    step1_keys = ["user_name", "user_species", "user_color"]
                    step2_keys = ["ai_name", "ai_subtitle", "ai_greeting", "ai_prompt"]
                    cur_keys = step1_keys if step == 1 else step2_keys
                    active_field = cur_keys[(cur_keys.index(active_field) + 1) % len(cur_keys)]
                elif event.unicode and ord(event.unicode) >= 32:
                    sfx_key.play()
                    fields[active_field] += event.unicode

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Check for field clicks to switch active focus dynamically
                fy_check = frame.y + 80
                form_keys = [("user_name", "Your Name"), ("user_species", "Species / Role"),
                             ("user_color", "Optic / Theme Color")] if step == 1 else [
                    ("ai_name", "AI Companion Name"), ("ai_subtitle", "Role / Subtitle"),
                    ("ai_greeting", "Opening Greeting"), ("ai_prompt", "System Persona Prompt")
                ]

                for key, _ in form_keys:
                    fh = 32 if key != "ai_prompt" else 90
                    f_rect = pygame.Rect(frame.x + 30, fy_check + 20, frame.width - 60, fh)
                    if f_rect.collidepoint(event.pos):
                        active_field = key
                        sfx_click.play()
                        break
                    fy_check += 60 if key != "ai_prompt" else 120

                # Check Next / Complete Button Click
                next_btn = pygame.Rect(frame.right - 160, frame.bottom - 50, 130, 35)
                if next_btn.collidepoint(event.pos):
                    sfx_send.play()
                    if step == 1 and fields["user_name"].strip():
                        step = 2
                        active_field = "ai_name"
                    elif step == 2 and fields["ai_name"].strip():
                        # Save User Persona
                        u_id = fields["user_name"].lower().replace(" ", "_") + "_user"
                        u_json = {
                            "id": u_id, "name": fields["user_name"],
                            "title": fields["user_species"] or "Operator",
                            "species": fields["user_species"] or "Operator",
                            "optic_color": fields["user_color"], "color": [0, 180, 255],
                            "lore": "Operator on local terminal node."
                        }
                        with open(os.path.join(USER_PERSONAS_DIR, f"{u_id}.json"), "w", encoding="utf-8") as f:
                            json.dump(u_json, f, indent=2)

                        # Save AI Persona
                        a_id = fields["ai_name"].lower().replace(" ", "_")
                        a_json = {
                            "id": a_id, "name": fields["ai_name"],
                            "subtitle": fields["ai_subtitle"] or "Autonomous AI",
                            "color": [0, 220, 160], "temperature": 0.70,
                            "greeting": fields["ai_greeting"] or "*system online*",
                            "base_prompt": fields["ai_prompt"] or f"You are {fields['ai_name']}."
                        }
                        with open(os.path.join(PERSONAS_DIR, f"{a_id}.json"), "w", encoding="utf-8") as f:
                            json.dump(a_json, f, indent=2)
                        return

        fy = frame.y + 80
        form_keys = [("user_name", "Your Name"), ("user_species", "Species / Role"),
                     ("user_color", "Optic / Theme Color")] if step == 1 else [
            ("ai_name", "AI Companion Name"), ("ai_subtitle", "Role / Subtitle"), ("ai_greeting", "Opening Greeting"),
            ("ai_prompt", "System Persona Prompt")
        ]

        for key, label in form_keys:
            is_act = (active_field == key)
            screen.blit(small_font.render(f"{label}:", True, SYSTEM_COLOR), (frame.x + 30, fy))

            fh = 32 if key != "ai_prompt" else 90
            f_rect = pygame.Rect(frame.x + 30, fy + 20, frame.width - 60, fh)
            pygame.draw.rect(screen, INPUT_BG, f_rect, border_radius=4)
            pygame.draw.rect(screen, (0, 220, 255) if is_act else BORDER_COLOR, f_rect, width=1, border_radius=4)

            val = fields[key] + ("|" if is_act and ((pygame.time.get_ticks() // 500) % 2 == 0) else "")
            screen.blit(font.render(val, True, TEXT_COLOR), (f_rect.x + 10, f_rect.y + 6))
            fy += 60 if key != "ai_prompt" else 120

        next_btn = pygame.Rect(frame.right - 160, frame.bottom - 50, 130, 35)
        pygame.draw.rect(screen, (0, 220, 255), next_btn, border_radius=4)
        btn_txt = "NEXT ->" if step == 1 else "COMPLETE"
        screen.blit(bold_font.render(btn_txt, True, (15, 17, 22)), (next_btn.x + 20, next_btn.y + 8))

        draw_crt_scanlines(screen, line_spacing=3, alpha=20)
        pygame.display.flip()


# ---------------------------------------------------------
# 10. INITIALIZATION & MAIN LOOP
# ---------------------------------------------------------
user_personas = load_all_user_personas()
ai_personas = load_all_ai_personas()

if not user_personas or not ai_personas:
    run_first_time_setup()
    user_personas = load_all_user_personas()
    ai_personas = load_all_ai_personas()

active_ai_id = list(ai_personas.keys())[0]
active_user_id = list(user_personas.keys())[0]
current_trust = load_relationship(active_ai_id)
active_messages = load_chat_history(active_ai_id, active_user_id)

input_text = ""
scroll_y = 0
is_generating = False
show_creator_modal = False
creator_fields = {"id": "", "name": "", "subtitle": "", "greeting": "", "prompt": ""}
active_field_key = "name"


def fetch_response_thread(ai_id, user_prompt):
    global is_generating, current_trust
    try:
        persona_temp = ai_personas[ai_id].get("temperature", 0.70)
        active_messages[0] = {"role": "system", "content": build_combined_system_prompt(ai_id, active_user_id)}
        payload_messages = get_trimmed_messages(active_messages, MAX_CONTEXT_MESSAGES)

        response = client.chat.completions.create(
            model="local-model",
            messages=payload_messages,
            temperature=persona_temp,
            top_p=0.9,
            max_tokens=250,
            presence_penalty=0.1,
            frequency_penalty=0.2
        )
        ai_reply = response.choices[0].message.content.strip()
        active_messages.append({"role": "assistant", "content": ai_reply})
        save_chat_history(ai_id, active_messages)

        trust_change = calculate_trust_delta(user_prompt, ai_reply)
        current_trust = max(0, min(100, current_trust + trust_change))
        save_relationship(ai_id, current_trust)

        sfx_receive.play()
    except Exception as e:
        print(f"API Error: {e}")
    finally:
        is_generating = False


running = True
cursor_timer = 0
sidebar_scroll = 0

while running:
    dt = clock.tick(60)
    cursor_timer += dt
    width, height = screen.get_size()

    current_ai = ai_personas[active_ai_id]
    current_user = user_personas[active_user_id]
    theme_accent = current_ai["color"]

    input_box_h = 100
    sidebar_rect = pygame.Rect(10, 10, 250, height - 20)
    header_rect = pygame.Rect(270, 10, width - 280, 50)
    input_rect = pygame.Rect(270, height - (input_box_h + 10), width - 280, input_box_h)
    chat_rect = pygame.Rect(270, 70, width - 280, height - (input_box_h + 90))

    mouse_pos = pygame.mouse.get_pos()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.MOUSEWHEEL:
            if not show_creator_modal:
                if chat_rect.collidepoint(mouse_pos):
                    scroll_y += event.y * 30
                elif sidebar_rect.collidepoint(mouse_pos):
                    sidebar_scroll += event.y * 20

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not show_creator_modal:
                create_btn = pygame.Rect(sidebar_rect.x + 10, sidebar_rect.y + 35, sidebar_rect.width - 20, 30)
                if create_btn.collidepoint(event.pos):
                    sfx_click.play()
                    show_creator_modal = True

                btn_y = sidebar_rect.y + 75 + sidebar_scroll
                for p_id in ai_personas.keys():
                    btn_rect = pygame.Rect(sidebar_rect.x + 10, btn_y, sidebar_rect.width - 20, 36)
                    if btn_rect.collidepoint(event.pos) and not is_generating:
                        if active_ai_id != p_id:
                            sfx_click.play()
                            save_chat_history(active_ai_id, active_messages)
                            active_ai_id = p_id
                            current_trust = load_relationship(active_ai_id)
                            active_messages = load_chat_history(active_ai_id, active_user_id)
                            scroll_y = -9999
                        break
                    btn_y += 42

        elif event.type == pygame.KEYDOWN and not is_generating and not show_creator_modal:
            keys_pressed = pygame.key.get_pressed()
            ctrl_held = keys_pressed[pygame.K_LCTRL] or keys_pressed[pygame.K_RCTRL]

            if ctrl_held and event.key == pygame.K_r:
                sfx_click.play()
                active_messages = reset_active_chat(active_ai_id, active_user_id)
                current_trust = load_relationship(active_ai_id)
                scroll_y = 0
                input_text = ""

            elif ctrl_held and event.key == pygame.K_e:
                sfx_send.play()
                exported_pkg = export_persona_as_chat_package(active_ai_id)
                active_messages.append({"role": "assistant",
                                        "content": f"[SYSTEM: Persona exported as .chat package to '{exported_pkg}']"})
                scroll_y = -9999

            elif event.key == pygame.K_RETURN:
                if keys_pressed[pygame.K_LSHIFT] or keys_pressed[pygame.K_RSHIFT]:
                    input_text += "\n"
                elif input_text.strip():
                    if not lm_studio_online:
                        active_messages.append({"role": "assistant",
                                                "content": "[SYSTEM ERROR: Unable to reach local LLM server at http://localhost:1234.]"})
                    else:
                        sfx_send.play()
                        user_prompt = input_text.strip()
                        input_text = ""
                        active_messages.append({"role": "user", "content": user_prompt})
                        save_chat_history(active_ai_id, active_messages)
                        is_generating = True
                        scroll_y = -9999
                        threading.Thread(target=fetch_response_thread, args=(active_ai_id, user_prompt),
                                         daemon=True).start()

            elif event.key == pygame.BACKSPACE:
                if len(input_text) > 0: sfx_key.play()
                input_text = input_text[:-1]
            elif event.unicode and ord(event.unicode) >= 32:
                sfx_key.play()
                input_text += event.unicode

    screen.fill(BG_COLOR)
    draw_terminal_panel(screen, sidebar_rect, BORDER_COLOR, fill_color=SIDEBAR_BG)
    screen.blit(bold_font.render("AI PERSONAS", True, SYSTEM_COLOR), (sidebar_rect.x + 15, sidebar_rect.y + 10))

    btn_y = sidebar_rect.y + 75 + sidebar_scroll
    for p_id, p_info in ai_personas.items():
        btn_rect = pygame.Rect(sidebar_rect.x + 10, btn_y, sidebar_rect.width - 20, 36)
        is_selected = (p_id == active_ai_id)
        pygame.draw.rect(screen, PANEL_BG if not is_selected else (35, 40, 52), btn_rect, border_radius=5)
        draw_glow_circle(screen, p_info["color"], (btn_rect.x + 16, btn_rect.centery), 3)
        pygame.draw.rect(screen, p_info["color"] if is_selected else BORDER_COLOR, btn_rect,
                         width=(2 if is_selected else 1), border_radius=5)
        screen.blit(font.render(p_info["name"], True, TEXT_COLOR if not is_selected else p_info["color"]),
                    (btn_rect.x + 30, btn_rect.y + 8))
        btn_y += 42

    draw_terminal_panel(screen, header_rect, theme_accent)
    draw_glow_circle(screen, theme_accent, (header_rect.x + 20, header_rect.y + 18), 4)
    screen.blit(bold_font.render(f"AGENT: {current_ai['name'].upper()}", True, theme_accent),
                (header_rect.x + 35, header_rect.y + 8))
    screen.blit(small_font.render(f"Operator: {current_user['name']} [{current_user['species']}]", True, USER_COLOR),
                (header_rect.x + 35, header_rect.y + 28))

    rank_title, rank_color = get_relationship_rank(current_trust)
    meter_x = header_rect.right - 230
    screen.blit(small_font.render(f"TRUST: {rank_title} ({current_trust}%)", True, rank_color),
                (meter_x, header_rect.y + 8))
    bar_bg = pygame.Rect(meter_x, header_rect.y + 28, 120, 8)
    pygame.draw.rect(screen, (30, 35, 45), bar_bg, border_radius=2)
    if current_trust > 0:
        pygame.draw.rect(screen, rank_color,
                         pygame.Rect(meter_x, header_rect.y + 28, int((current_trust / 100.0) * 120), 8),
                         border_radius=2)

    draw_terminal_panel(screen, chat_rect, BORDER_COLOR)
    rendered_lines = []
    for msg in active_messages:
        if msg["role"] == "system": continue
        prefix = f"{current_user['name'].upper()}: " if msg["role"] == "user" else f"{current_ai['name'].upper()}: "
        color = current_user["color"] if msg["role"] == "user" else theme_accent
        rendered_lines.append((prefix, color, True))
        for line in wrap_text(msg["content"], font, chat_rect.width - 40):
            rendered_lines.append((line, TEXT_COLOR, False))
        rendered_lines.append(("", TEXT_COLOR, False))

    tot_height = len(rendered_lines) * LINE_SPACING
    min_scroll = min(0, chat_rect.height - tot_height - 20)
    scroll_y = min_scroll if scroll_y == -9999 else max(min_scroll, min(0, scroll_y))

    chat_clip = screen.get_clip()
    screen.set_clip(chat_rect)
    y_off = chat_rect.y + 15 + scroll_y
    for text, color, is_hdr in rendered_lines:
        if chat_rect.y - LINE_SPACING <= y_off <= chat_rect.bottom:
            screen.blit((bold_font if is_hdr else font).render(text, True, color), (chat_rect.x + 20, y_off))
        y_off += LINE_SPACING
    screen.set_clip(chat_clip)

    draw_terminal_panel(screen, input_rect, theme_accent if not is_generating else BORDER_COLOR, fill_color=INPUT_BG)
    if is_generating:
        screen.blit(font.render(f"[ {current_ai['name']} is generating response... ]", True, SYSTEM_COLOR),
                    (input_rect.x + 15, input_rect.y + 15))
    else:
        input_lines = wrap_text(input_text, font, input_rect.width - 30)
        if not input_lines or input_lines == ['']:
            screen.blit(
                font.render("Enter message... (Shift+Enter: newline | Enter: send | Ctrl+E: export .chat)", True,
                            SYSTEM_COLOR), (input_rect.x + 15, input_rect.y + 15))
        else:
            iy = input_rect.y + 12
            for idx, l in enumerate(input_lines):
                if idx == len(input_lines) - 1 and (cursor_timer % 1000 < 500): l += "|"
                screen.blit(font.render(l, True, TEXT_COLOR), (input_rect.x + 15, iy))
                iy += 20

    draw_crt_scanlines(screen, line_spacing=3, alpha=20)
    pygame.display.flip()

pygame.quit()
sys.exit()