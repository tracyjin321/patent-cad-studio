import html
import math
from typing import Any


def _svg(content: str, title: str) -> str:
    safe = html.escape(title)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 620" role="img" aria-label="{safe}">
<defs><marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#667085"/></marker><style>.o{{fill:none;stroke:#17202a;stroke-width:2.4;stroke-linejoin:round}}.h{{fill:none;stroke:#667085;stroke-width:1.2;stroke-dasharray:7 5}}.d{{fill:none;stroke:#667085;stroke-width:1.1;marker-start:url(#arrow);marker-end:url(#arrow)}}.t{{font:14px sans-serif;fill:#344054}}.n{{font:13px sans-serif;fill:#7b2d8e}}</style></defs>
<rect width="900" height="620" fill="#fff"/><text x="36" y="40" class="t">{safe}</text>{content}
<text x="36" y="590" class="t">技术附图 · 比例示意 · 单位 mm</text></svg>"""


def _dimension(x1: float, y1: float, x2: float, y2: float, label: str) -> str:
    return f'<path class="d" d="M{x1} {y1}L{x2} {y2}"/><text class="t" x="{(x1+x2)/2}" y="{(y1+y2)/2-8}" text-anchor="middle">{html.escape(label)}</text>'


def bearing(p: dict[str, Any]) -> str:
    count = max(6, min(16, int(p["rolling_elements"])))
    balls = "".join(
        f'<circle class="o" cx="{450+130*math.cos(2*math.pi*i/count):.1f}" cy="{310+130*math.sin(2*math.pi*i/count):.1f}" r="19"/>'
        for i in range(count)
    )
    return _svg(f'<circle class="o" cx="450" cy="310" r="205"/><circle class="o" cx="450" cy="310" r="165"/>{balls}<circle class="o" cx="450" cy="310" r="92"/><path class="h" d="M180 310H720M450 55V565"/>{_dimension(245,545,655,545,f"⌀{p['outer_diameter']}")}', "滚动轴承")


def flange(p: dict[str, Any]) -> str:
    count = max(4, min(16, int(p["bolt_holes"])))
    holes = "".join(f'<circle class="o" cx="{450+145*math.cos(2*math.pi*i/count):.1f}" cy="{310+145*math.sin(2*math.pi*i/count):.1f}" r="17"/>' for i in range(count))
    return _svg(f'<circle class="o" cx="450" cy="310" r="210"/><circle class="h" cx="450" cy="310" r="145"/>{holes}<circle class="o" cx="450" cy="310" r="84"/><path class="h" d="M190 310H710M450 50V570"/>{_dimension(240,550,660,550,f"⌀{p['outer_diameter']}")}', "圆形法兰")


def valve(p: dict[str, Any]) -> str:
    c = f'<path class="o" d="M130 260H275L330 205H570L625 260H770V390H625L570 445H330L275 390H130Z"/><path class="o" d="M330 205Q450 350 570 205M330 445Q450 300 570 445"/><path class="o" d="M420 205V120H480V205M365 120H535M390 90H510M450 90V45"/><circle class="o" cx="450" cy="67" r="72"/><path class="h" d="M450 170V470"/>{_dimension(130,500,770,500,f"{p['body_length']}")}'
    return _svg(c, "截止阀")


def shaft(p: dict[str, Any]) -> str:
    c = '<path class="o" d="M100 280H220V235H360V195H555V245H680V275H800V345H680V375H555V425H360V385H220V340H100Z"/><path class="h" d="M70 310H830"/><rect class="o" x="400" y="195" width="95" height="22"/>' + _dimension(100,500,800,500,f"{p['total_length']}")
    return _svg(c, "阶梯轴系")


def gear(p: dict[str, Any]) -> str:
    teeth = max(10, min(40, int(p["teeth"])))
    points = []
    for i in range(teeth * 2):
        radius = 220 if i % 2 == 0 else 195
        angle = -math.pi / 2 + math.pi * i / teeth
        points.append(f"{450+radius*math.cos(angle):.1f},{310+radius*math.sin(angle):.1f}")
    c = f'<polygon class="o" points="{" ".join(points)}"/><circle class="o" cx="450" cy="310" r="165"/><circle class="o" cx="450" cy="310" r="65"/><rect class="o" x="440" y="245" width="20" height="50"/><path class="h" d="M180 310H720M450 45V575"/>{_dimension(230,560,670,560,f"m={p['module']} · z={p['teeth']}")}'
    return _svg(c, "直齿圆柱齿轮")


def screw(p: dict[str, Any]) -> str:
    waves = []
    for x in range(170, 735, 22):
        waves.append(f"M{x} 240L{x+18} 380M{x+8} 240L{x+26} 380")
    c = f'<path class="o" d="M90 275H150V240H750V275H810V345H750V380H150V345H90Z"/><path class="o" d="{" ".join(waves)}"/><path class="h" d="M70 310H830"/>{_dimension(150,455,750,455,f"{p['length']} · 导程 {p['lead']}")}'
    return _svg(c, "精密丝杠")


def coupling(p: dict[str, Any]) -> str:
    bolts = max(4, min(12, int(p["bolts"])))
    ys = [215 + i * 190 / max(1, bolts // 2 - 1) for i in range(max(2, bolts // 2))]
    circles = "".join(f'<circle class="o" cx="{x}" cy="{y:.1f}" r="12"/>' for x in (350, 550) for y in ys)
    c = f'<path class="o" d="M110 270H280V175H390V220H510V175H620V270H790V350H620V445H510V400H390V445H280V350H110Z"/>{circles}<path class="h" d="M70 310H830"/>{_dimension(280,500,620,500,f"{p['length']}")}'
    return _svg(c, "法兰联轴器")


def seal(p: dict[str, Any]) -> str:
    c = f'<path class="o" d="M225 175H675V445H225Z"/><path class="o" d="M285 230H615V390H285Z"/><path class="o" d="M285 230L375 310L285 390M615 230L525 310L615 390"/><circle class="o" cx="450" cy="310" r="66"/><path class="h" d="M180 310H720M450 120V500"/>{_dimension(225,500,675,500,f"⌀{p['outer_diameter']} / ⌀{p['inner_diameter']}")}'
    return _svg(c, "唇形密封件")


GENERATORS = {"bearing": bearing, "flange": flange, "valve": valve, "shaft": shaft, "gear": gear, "screw": screw, "coupling": coupling, "seal": seal}


def generate_svg(part_type: str, parameters: dict[str, Any]) -> str:
    return GENERATORS[part_type](parameters)

