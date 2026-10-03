"""Generates the flat product illustrations used as demo product images."""
import os
import sys

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)

NAVY, GREEN, GREEN_D, GOLD, RED = '#0f172a', '#10b981', '#059669', '#f59e0b', '#ef4444'
YELLOW, SLATE = '#d9f24b', '#64748b'
FONT = 'font-family="Arial,Helvetica,sans-serif"'


def svg(body, bg=('#f1f5f9', '#e2e8f0'), shadow=True):
    sh = '<ellipse cx="300" cy="528" rx="150" ry="16" fill="#0f172a" opacity=".12"/>' if shadow else ''
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600" width="600" height="600">'
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/></linearGradient></defs>'
        '<rect width="600" height="600" fill="url(#bg)"/>%s%s</svg>' % (bg[0], bg[1], sh, body))


SHOP = ('#ecfdf5', '#d1fae5')
SKY = ('#eff6ff', '#dbeafe')
BAR = ('#fffbeb', '#fef3c7')
COOL = ('#f0f9ff', '#e0f2fe')


def strings(cx, cy, rx, ry, step=26, color='#94a3b8', w=2.5, cid='c'):
    lines = []
    x = cx - rx
    while x <= cx + rx:
        lines.append('<line x1="%s" y1="%s" x2="%s" y2="%s"/>' % (x, cy - ry, x, cy + ry))
        x += step
    y = cy - ry
    while y <= cy + ry:
        lines.append('<line x1="%s" y1="%s" x2="%s" y2="%s"/>' % (cx - rx, y, cx + rx, y))
        y += step
    return ('<clipPath id="%s"><ellipse cx="%s" cy="%s" rx="%s" ry="%s"/></clipPath>'
            '<g clip-path="url(#%s)" stroke="%s" stroke-width="%s">%s</g>'
            % (cid, cx, cy, rx, ry, cid, color, w, ''.join(lines)))


def racket(frame, grip, angle=35, ry=135):
    return (
        '<g transform="rotate(%d 300 300)">%s'
        '<ellipse cx="300" cy="215" rx="100" ry="%d" fill="none" stroke="%s" stroke-width="16"/>'
        '<path d="M255 338 L282 400 M345 338 L318 400" stroke="%s" stroke-width="14" fill="none" stroke-linecap="round"/>'
        '<rect x="283" y="395" width="34" height="150" rx="12" fill="%s"/>'
        '<rect x="283" y="395" width="34" height="150" rx="12" fill="none" stroke="%s" stroke-opacity=".25" stroke-width="3"/>'
        '<path d="M283 430 L317 418 M283 458 L317 446 M283 486 L317 474 M283 514 L317 502" stroke="#fff" stroke-opacity=".35" stroke-width="4"/>'
        '</g>' % (angle, strings(300, 215, 100, ry, cid='rk'), ry, frame, frame, grip, NAVY))


def ball(cx, cy, r, color=YELLOW, seam='#fff'):
    sw = max(3, round(r / 14))
    a, b, c = round(r * 0.72), round(r * 0.7), round(r * 0.1)
    d = round(r * 0.25)
    return (
        '<circle cx="%d" cy="%d" r="%d" fill="%s"/>'
        '<path d="M%d %d C%d %d %d %d %d %d" fill="none" stroke="%s" stroke-width="%d" stroke-linecap="round"/>'
        '<path d="M%d %d C%d %d %d %d %d %d" fill="none" stroke="%s" stroke-width="%d" stroke-linecap="round"/>'
        '<circle cx="%d" cy="%d" r="%d" fill="none" stroke="%s" stroke-opacity=".12" stroke-width="3"/>'
        % (cx, cy, r, color,
           cx - a, cy - b, cx - c, cy - d, cx - c, cy + d, cx - a, cy + b, seam, sw,
           cx + a, cy - b, cx + c, cy - d, cx + c, cy + d, cx + a, cy + b, seam, sw,
           cx, cy, r, NAVY))


def can_of_balls(cx, label, balls=3, cap='#dc2626'):
    h = 60 * balls + 30
    top = 505 - h
    return (
        '<rect x="%d" y="%d" width="104" height="%d" rx="16" fill="#1e293b"/>'
        '<rect x="%d" y="%d" width="104" height="26" rx="10" fill="%s"/>'
        '<rect x="%d" y="%d" width="80" height="60" rx="8" fill="#fff" opacity=".95"/>'
        '<text x="%d" y="%d" %s font-weight="800" font-size="20" text-anchor="middle" fill="%s">%s</text>'
        '<rect x="%d" y="%d" width="10" height="%d" rx="5" fill="#fff" opacity=".12"/>'
        % (cx - 52, top, h, cx - 52, top - 14, cap, cx - 40, top + h // 2 - 30,
           cx, top + h // 2 + 6, FONT, NAVY, label, cx - 40, top + 10, h - 20))


F = {}

F['tennis_racket'] = svg(racket(NAVY, GREEN), SHOP)

dots = ''.join('<circle cx="%d" cy="%d" r="9"/>' % (x, y)
               for y in (130, 175, 220, 265) for x in (240, 285, 330, 375)
               if not (y == 130 and x in (240, 375)))
F['padel_racket'] = svg(
    '<g transform="rotate(32 300 300)">'
    '<path d="M300 70 C405 70 440 150 430 235 C422 305 372 345 335 360 L335 395 L265 395 L265 360 '
    'C228 345 178 305 170 235 C160 150 195 70 300 70 Z" fill="#f97316" stroke="%s" stroke-width="12"/>'
    '<g fill="#fff" opacity=".85">%s</g>'
    '<rect x="272" y="392" width="56" height="140" rx="14" fill="%s"/>'
    '<path d="M272 430 L328 418 M272 460 L328 448 M272 490 L328 478" stroke="#fff" stroke-opacity=".3" stroke-width="5"/>'
    '</g>' % (NAVY, dots, NAVY), SKY)

F['badminton_racket'] = svg(
    '<g transform="rotate(35 300 300)">%s'
    '<ellipse cx="300" cy="190" rx="78" ry="118" fill="none" stroke="#dc2626" stroke-width="14"/>'
    '<path d="M300 308 L300 385" stroke="#dc2626" stroke-width="12" stroke-linecap="round"/>'
    '<path d="M258 282 L300 330 L342 282" stroke="#dc2626" stroke-width="10" fill="none"/>'
    '<rect x="288" y="380" width="24" height="150" rx="10" fill="%s"/>'
    '<path d="M288 420 L312 410 M288 448 L312 438 M288 476 L312 466" stroke="#fff" stroke-opacity=".35" stroke-width="4"/>'
    '</g>' % (strings(300, 190, 78, 118, step=22, color='#cbd5e1', w=2, cid='bd'), NAVY), SKY)

F['tennis_balls'] = svg(can_of_balls(210, 'TENNIS') + ball(400, 470, 52) + ball(470, 505, 40) + ball(345, 505, 36), SHOP)
F['padel_balls'] = svg(can_of_balls(300, 'PADEL', cap=GREEN_D) + ball(150, 495, 42, '#a3e635') + ball(455, 490, 46, '#a3e635'), SKY)

cock = ''
for dx, dy, a in ((-110, 20, -18), (110, 10, 16), (0, 40, 0)):
    cock += (
        '<g transform="translate(%d %d) rotate(%d 300 300)">'
        '<path d="M300 190 L228 430 Q300 462 372 430 Z" fill="#fff" stroke="#cbd5e1" stroke-width="4"/>'
        '<g stroke="#cbd5e1" stroke-width="3"><path d="M300 190 L262 440 M300 190 L300 450 M300 190 L338 440 M300 190 L246 436 M300 190 L354 436"/></g>'
        '<path d="M232 418 Q300 450 368 418" fill="none" stroke="%s" stroke-width="10"/>'
        '<circle cx="300" cy="175" r="36" fill="#fde68a" stroke="#d97706" stroke-width="5"/>'
        '</g>' % (dx, dy, a, GOLD))
F['shuttlecocks'] = svg(cock, SKY)

F['cricket_bat'] = svg(
    '<g transform="rotate(32 300 300)">'
    '<rect x="262" y="40" width="76" height="76" rx="14" fill="#7c4a1d"/>'
    '<rect x="272" y="40" width="56" height="60" rx="10" fill="#8b5a2b"/>'
    '<path d="M238 190 Q238 150 262 130 L338 130 Q362 150 362 190 L362 440 Q362 470 332 470 L268 470 Q238 470 238 440 Z" fill="#f3d9a4" stroke="#b78a48" stroke-width="6"/>'
    '<path d="M300 140 L300 462" stroke="#d6b36f" stroke-width="5"/>'
    '<path d="M262 160 L262 450 M338 160 L338 450" stroke="#e7c98a" stroke-width="4"/>'
    '<rect x="283" y="118" width="34" height="30" fill="#b78a48"/>'
    '<rect x="268" y="40" width="64" height="12" rx="4" fill="%s"/>'
    '<path d="M268 62 L332 56 M268 78 L332 72 M268 94 L332 88" stroke="#fff" stroke-opacity=".45" stroke-width="4"/>'
    '</g>' % RED, SHOP)

F['grip_tape'] = svg(
    '<ellipse cx="300" cy="410" rx="150" ry="52" fill="#065f46"/>'
    '<rect x="150" y="270" width="300" height="140" fill="%s"/>'
    '<ellipse cx="300" cy="270" rx="150" ry="52" fill="#34d399"/>'
    '<ellipse cx="300" cy="270" rx="64" ry="20" fill="#ecfdf5"/>'
    '<path d="M150 330 Q300 382 450 330 M150 360 Q300 412 450 360" stroke="#fff" stroke-opacity=".35" stroke-width="5" fill="none"/>'
    '<path d="M450 395 C500 420 520 460 548 470" stroke="%s" stroke-width="40" stroke-linecap="round" fill="none"/>'
    % (GREEN, GREEN), SHOP)

fringe = ''.join('<line x1="%d" y1="470" x2="%d" y2="498"/>' % (x, x) for x in range(160, 450, 16))
F['towel'] = svg(
    '<rect x="145" y="150" width="310" height="320" rx="18" fill="#f8fafc" stroke="#cbd5e1" stroke-width="4"/>'
    '<rect x="145" y="150" width="310" height="34" fill="%s"/>'
    '<rect x="145" y="190" width="310" height="10" fill="%s"/>'
    '<rect x="145" y="420" width="310" height="10" fill="%s"/>'
    '<rect x="145" y="436" width="310" height="34" fill="%s"/>'
    '<g stroke="#e2e8f0" stroke-width="4" stroke-linecap="round">%s</g>'
    '<text x="300" y="330" %s font-weight="800" font-size="30" text-anchor="middle" fill="%s">THE CHAMPIONS</text>'
    '<text x="300" y="366" %s font-weight="800" font-size="30" text-anchor="middle" fill="%s">CLUB</text>'
    % (GREEN, NAVY, NAVY, GREEN, fringe, FONT, NAVY, FONT, GREEN_D), SHOP)

# ---- bar and cafeteria
F['water_bottle'] = svg(
    '<rect x="262" y="70" width="76" height="46" rx="10" fill="%s"/>'
    '<path d="M270 112 L330 112 L330 142 Q380 175 380 235 L380 480 Q380 520 340 520 L260 520 Q220 520 220 480 L220 235 Q220 175 270 142 Z" fill="#bae6fd" fill-opacity=".75" stroke="#38bdf8" stroke-width="6"/>'
    '<path d="M220 300 L380 300 L380 480 Q380 520 340 520 L260 520 Q220 520 220 480 Z" fill="#38bdf8" fill-opacity=".55"/>'
    '<rect x="228" y="340" width="144" height="86" fill="#fff" opacity=".92"/>'
    '<text x="300" y="380" %s font-weight="800" font-size="24" text-anchor="middle" fill="#0369a1">WATER</text>'
    '<text x="300" y="408" %s font-weight="600" font-size="16" text-anchor="middle" fill="%s">500 ml</text>'
    '<rect x="240" y="170" width="14" height="140" rx="7" fill="#fff" opacity=".5"/>'
    % (NAVY, FONT, FONT, SLATE), COOL)

F['cold_coffee'] = svg(
    '<path d="M200 150 L400 150 L370 500 Q368 520 348 520 L252 520 Q232 520 230 500 Z" fill="#fff" fill-opacity=".6" stroke="#a16207" stroke-width="6"/>'
    '<path d="M208 240 L392 240 L370 500 Q368 520 348 520 L252 520 Q232 520 230 500 Z" fill="#7c4a1d"/>'
    '<path d="M208 240 L392 240 L388 290 L212 290 Z" fill="#fde7c0"/>'
    '<rect x="262" y="320" width="56" height="56" rx="10" fill="#fff" opacity=".35" transform="rotate(14 290 348)"/>'
    '<rect x="318" y="380" width="56" height="56" rx="10" fill="#fff" opacity=".3" transform="rotate(-10 346 408)"/>'
    '<rect x="285" y="60" width="18" height="320" rx="9" fill="%s" transform="rotate(14 294 220)"/>'
    '<rect x="188" y="136" width="224" height="22" rx="10" fill="#fef3c7" stroke="#a16207" stroke-width="4"/>'
    % GREEN, BAR)


def cup(fill_color, foam=None, art=False):
    foam_svg = '<ellipse cx="300" cy="300" rx="120" ry="30" fill="%s"/>' % foam if foam else ''
    heart = ('<path d="M300 318 C262 296 282 270 300 288 C318 270 338 296 300 318 Z" fill="#a16207" opacity=".7"/>'
             if art else '')
    return (
        '<ellipse cx="300" cy="500" rx="190" ry="36" fill="#e2e8f0"/><ellipse cx="300" cy="494" rx="170" ry="28" fill="#fff"/>'
        '<path d="M170 290 L430 290 Q430 470 300 470 Q170 470 170 290 Z" fill="#fff" stroke="#cbd5e1" stroke-width="6"/>'
        '<path d="M425 320 Q505 320 495 385 Q485 440 410 430" fill="none" stroke="#cbd5e1" stroke-width="22" stroke-linecap="round"/>'
        '<ellipse cx="300" cy="290" rx="130" ry="34" fill="#fff" stroke="#cbd5e1" stroke-width="6"/>'
        '<ellipse cx="300" cy="294" rx="116" ry="26" fill="%s"/>%s%s'
        '<path d="M250 230 Q232 200 252 170 Q272 140 250 110 M310 230 Q292 200 312 170 Q332 140 310 110 M370 230 Q352 200 372 170 Q392 140 370 110" '
        'fill="none" stroke="#94a3b8" stroke-opacity=".55" stroke-width="8" stroke-linecap="round"/>'
        % (fill_color, foam_svg, heart))


F['espresso'] = svg(cup('#4a2c0f'), BAR, shadow=False)
F['cappuccino'] = svg(cup('#b57a3a', foam='#f5deb3', art=True), BAR, shadow=False)

F['energy_drink'] = svg(
    '<rect x="225" y="95" width="150" height="425" rx="26" fill="%s"/>'
    '<rect x="240" y="80" width="120" height="30" rx="10" fill="#94a3b8"/>'
    '<rect x="225" y="190" width="150" height="190" fill="%s"/>'
    '<path d="M312 205 L262 310 L298 310 L286 372 L342 262 L304 262 Z" fill="#fff"/>'
    '<text x="300" y="440" %s font-weight="800" font-size="26" text-anchor="middle" fill="#fff">ENERGY</text>'
    '<text x="300" y="468" %s font-weight="600" font-size="14" text-anchor="middle" fill="#94a3b8">250 ml</text>'
    '<rect x="238" y="120" width="12" height="380" rx="6" fill="#fff" opacity=".12"/>'
    % (NAVY, GREEN, FONT, FONT), ('#f0fdf4', '#dcfce7'))

bubbles = ''.join('<circle cx="%d" cy="%d" r="%d"/>' % b
                  for b in ((270, 330, 9), (320, 380, 12), (290, 440, 8), (345, 310, 7), (260, 400, 6), (340, 455, 10)))
segments = ''.join('<line x1="372" y1="170" x2="%d" y2="%d"/>' % (372 + 46 * c, 170 + 46 * s)
                   for c, s in ((1, 0), (.5, .87), (-.5, .87), (-1, 0), (-.5, -.87), (.5, -.87)))
F['lime_soda'] = svg(
    '<path d="M205 170 L395 170 L368 495 Q366 518 344 518 L256 518 Q234 518 232 495 Z" fill="#ecfccb" fill-opacity=".8" stroke="#84cc16" stroke-width="6"/>'
    '<path d="M214 250 L386 250 L368 495 Q366 518 344 518 L256 518 Q234 518 232 495 Z" fill="#bef264" fill-opacity=".85"/>'
    '<g fill="#fff" fill-opacity=".7">%s</g>'
    '<circle cx="372" cy="170" r="62" fill="#a3e635" stroke="#65a30d" stroke-width="6"/>'
    '<circle cx="372" cy="170" r="46" fill="#ecfccb"/>'
    '<g stroke="#a3e635" stroke-width="4">%s</g>'
    '<rect x="288" y="70" width="14" height="260" rx="7" fill="#ef4444" transform="rotate(12 295 200)"/>'
    % (bubbles, segments), ('#f7fee7', '#ecfccb'))

F['sandwich'] = svg(
    '<path d="M130 340 L300 230 L470 340 L300 450 Z" fill="#f3d9a4" stroke="#c9a15a" stroke-width="5" stroke-linejoin="round"/>'
    '<path d="M130 340 L300 450 L300 500 L130 390 Z" fill="#e0b979"/><path d="M470 340 L300 450 L300 500 L470 390 Z" fill="#d4a85f"/>'
    '<path d="M130 320 L300 210 L470 320 L300 430 Z" fill="%s" stroke="%s" stroke-width="4"/>'
    '<path d="M130 295 L300 185 L470 295 L300 405 Z" fill="#fb7185"/>'
    '<path d="M130 270 L300 160 L470 270 L300 380 Z" fill="#fde68a"/>'
    '<path d="M130 245 L300 135 L470 245 L300 355 Z" fill="#f3d9a4" stroke="#c9a15a" stroke-width="5" stroke-linejoin="round"/>'
    '<path d="M200 235 L225 218 M290 190 L315 172 M360 230 L385 212" stroke="#c9a15a" stroke-width="6" stroke-linecap="round"/>'
    % (GREEN, GREEN_D), BAR)

F['protein_shake'] = svg(
    '<rect x="215" y="150" width="170" height="365" rx="38" fill="#fff" stroke="#cbd5e1" stroke-width="6"/>'
    '<path d="M215 215 L385 215 L385 477 Q385 515 347 515 L253 515 Q215 515 215 477 Z" fill="#92400e" fill-opacity=".9"/>'
    '<rect x="215" y="215" width="170" height="30" fill="#b45309"/>'
    '<rect x="225" y="276" width="150" height="120" rx="14" fill="#fff" opacity=".95"/>'
    '<text x="300" y="322" %s font-weight="800" font-size="28" text-anchor="middle" fill="%s">PROTEIN</text>'
    '<text x="300" y="356" %s font-weight="800" font-size="22" text-anchor="middle" fill="%s">SHAKE</text>'
    '<text x="300" y="382" %s font-weight="600" font-size="14" text-anchor="middle" fill="%s">25 g protein</text>'
    '<rect x="205" y="112" width="190" height="52" rx="16" fill="%s"/>'
    '<rect x="228" y="165" width="14" height="330" rx="7" fill="#fff" opacity=".35"/>'
    % (FONT, NAVY, FONT, GREEN_D, FONT, SLATE, NAVY), BAR)

seeds = ''.join('<ellipse cx="%d" cy="%d" rx="12" ry="6" transform="rotate(%d %d %d)"/>' % (x, y, a, x, y)
                for x, y, a in ((230, 210, -20), (300, 185, 0), (370, 210, 20), (265, 255, -10), (335, 255, 10)))
F['burger'] = svg(
    '<path d="M130 305 Q130 150 300 150 Q470 150 470 305 Z" fill="#e0a458" stroke="#b9792d" stroke-width="5"/>'
    '<g fill="#fff3d6">%s</g>'
    '<path d="M120 305 Q150 335 180 305 Q215 335 250 305 Q285 335 320 305 Q355 335 390 305 Q425 335 480 305 L480 322 L120 322 Z" fill="#65a30d"/>'
    '<rect x="125" y="322" width="350" height="44" rx="22" fill="#7c2d12"/>'
    '<path d="M115 366 L485 366 L455 412 L330 394 L300 420 L270 394 L145 412 Z" fill="#fbbf24"/>'
    '<rect x="120" y="402" width="360" height="26" rx="13" fill="#ef4444"/>'
    '<path d="M130 428 L470 428 Q470 495 400 495 L200 495 Q130 495 130 428 Z" fill="#e0a458" stroke="#b9792d" stroke-width="5"/>'
    % seeds, BAR)

F['wrap'] = svg(
    '<g transform="rotate(-18 300 320)">'
    '<path d="M180 190 L420 190 L420 480 Q420 510 390 510 L210 510 Q180 510 180 480 Z" fill="#f3d9a4" stroke="#c9a15a" stroke-width="6"/>'
    '<path d="M205 190 Q300 130 395 190 Z" fill="%s"/>'
    '<ellipse cx="300" cy="190" rx="110" ry="36" fill="#fb7185"/>'
    '<ellipse cx="300" cy="188" rx="86" ry="26" fill="#fde68a"/>'
    '<ellipse cx="300" cy="186" rx="60" ry="17" fill="#fff7ed"/>'
    '<path d="M180 330 L420 290 L420 340 L180 380 Z" fill="#f8fafc" opacity=".55"/>'
    '<path d="M180 400 L420 360" stroke="#c9a15a" stroke-width="5" opacity=".6"/>'
    '</g>' % GREEN, BAR)

for key, content in F.items():
    with open(os.path.join(OUT, key + '.svg'), 'w', encoding='utf-8') as fh:
        fh.write(content)
print(len(F), 'images')
