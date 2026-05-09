"""
=============================================================
 MStopografia — FIELD TO FINISH
 Gerador automático de DXF a partir de pontos topográficos
=============================================================

 Lê ficheiro TXT com formato: P,X,Y,Z,Código
 Gera ficheiro DXF com:
   - Polylines 3D entre pontos do mesmo código (linhas)
   - Símbolos (círculo + texto) para pontos isolados
   - Curvas de nível por triangulação TIN
   - Numeração e cotagem automática de todos os pontos

 DEPENDÊNCIAS:
   pip install ezdxf scipy numpy matplotlib

 USO:
   python topo_field2finish.py pontos.txt resultado.dxf

 PERSONALIZAÇÃO:
   Edita o dicionário CODIGOS abaixo para adicionar/alterar códigos.

 © 2026 Mário Sousa — MStopografia
=============================================================
"""

import sys
import ezdxf
import numpy as np
from scipy.interpolate import LinearNDInterpolator
import matplotlib.pyplot as plt


# ─────────────────────────────────────────────────────────────
# TABELA DE CÓDIGOS — edita aqui as tuas regras
#
# Formato:
#   "CÓDIGO": {
#       "tipo":    "linha"          → liga pontos em polyline
#                  "simbolo"        → ponto isolado com círculo
#                  "linha+simbolo"  → liga E marca cada ponto
#       "layer":   nome da layer no DXF
#       "cor":     número de cor AutoCAD
#                  (1=red, 2=yellow, 3=green, 4=cyan,
#                   5=blue, 6=magenta, 7=white)
#       "desc":    descrição legível
#   }
# ─────────────────────────────────────────────────────────────

CODIGOS = {
    # ── LINHAS ──────────────────────────────────────────────
    "MN":  {"tipo": "linha",          "layer": "MUROS",        "cor": 1,  "desc": "Muro"},
    "VL":  {"tipo": "linha",          "layer": "VALAS",        "cor": 4,  "desc": "Vala / Rego"},
    "BE":  {"tipo": "linha",          "layer": "BERMAS",       "cor": 2,  "desc": "Berma de estrada"},
    "EX":  {"tipo": "linha",          "layer": "EIXO_ESTRADA", "cor": 3,  "desc": "Eixo de estrada"},
    "CH":  {"tipo": "linha",          "layer": "CAMINHOS",     "cor": 30, "desc": "Caminho"},
    "ED":  {"tipo": "linha",          "layer": "EDIFICIOS",    "cor": 6,  "desc": "Edifício / Construção"},
    "LT":  {"tipo": "linha",          "layer": "LOTES",        "cor": 5,  "desc": "Limite de lote"},
    "LC":  {"tipo": "linha",          "layer": "LINHAS_AGUA",  "cor": 4,  "desc": "Linha de água"},
    "CV":  {"tipo": "linha",          "layer": "CAMINHOS_VEG", "cor": 62, "desc": "Caminho vegetal"},

    # ── SÍMBOLOS ────────────────────────────────────────────
    "AR":  {"tipo": "simbolo",        "layer": "ARVORES",      "cor": 3,  "desc": "Árvore"},
    "AR1": {"tipo": "simbolo",        "layer": "ARVORES",      "cor": 3,  "desc": "Árvore (isolada)"},
    "CX":  {"tipo": "simbolo",        "layer": "CAIXAS",       "cor": 7,  "desc": "Caixa (saneamento)"},
    "CXE": {"tipo": "simbolo",        "layer": "CAIXAS_ELEC",  "cor": 2,  "desc": "Caixa eléctrica"},
    "CXS": {"tipo": "simbolo",        "layer": "CAIXAS_SAN",   "cor": 1,  "desc": "Caixa saneamento"},
    "CXA": {"tipo": "simbolo",        "layer": "CAIXAS_AGUA",  "cor": 4,  "desc": "Caixa de água"},
    "PH":  {"tipo": "simbolo",        "layer": "POSTES",       "cor": 2,  "desc": "Poste (eletricidade)"},
    "PE":  {"tipo": "simbolo",        "layer": "POSTES_ELEC",  "cor": 2,  "desc": "Poste eléctrico"},
    "BC":  {"tipo": "simbolo",        "layer": "BOCAS_INCEND", "cor": 1,  "desc": "Boca de incêndio"},
    "MR":  {"tipo": "simbolo",        "layer": "MARCOS",       "cor": 7,  "desc": "Marco geodésico"},
    "PZ":  {"tipo": "simbolo",        "layer": "POCOS",        "cor": 4,  "desc": "Poço"},

    # ── LINHA + SÍMBOLO ─────────────────────────────────────
    "GU":  {"tipo": "linha+simbolo",  "layer": "GUARDAS",      "cor": 7,  "desc": "Guarda / Rail"},
    "CE":  {"tipo": "linha+simbolo",  "layer": "CERCAS",       "cor": 30, "desc": "Cerca / Vedação"},

    # ── PONTOS COTADOS (apenas cota, sem ligar) ─────────────
    "PT":  {"tipo": "simbolo",        "layer": "PONTOS_COTA",  "cor": 7,  "desc": "Ponto cotado"},
    "TC":  {"tipo": "simbolo",        "layer": "TERRENO",      "cor": 7,  "desc": "Ponto de terreno"},
}

# Raio do círculo para símbolos (em metros / unidades do desenho)
RAIO_SIMBOLO = 0.3

# ─────────────────────────────────────────────────────────────
# CURVAS DE NÍVEL
# ─────────────────────────────────────────────────────────────
INTERVALO_CURVAS    = 1.0   # intervalo entre curvas (metros)
INTERVALO_MESTRAS   = 5.0   # intervalo curvas mestras (metros)
LAYER_CURVAS        = "CURVAS_NIVEL"
LAYER_CURVAS_MESTRA = "CURVAS_MESTRAS"
COR_CURVAS          = 30    # laranja
COR_CURVAS_MESTRA   = 1     # vermelho


# =============================================================
# FUNÇÕES PRINCIPAIS
# =============================================================

def ler_pontos(ficheiro):
    """Lê ficheiro TXT com formato P,X,Y,Z,Código"""
    pontos = []
    with open(ficheiro, "r", encoding="utf-8-sig") as f:
        for n_linha, linha in enumerate(f, 1):
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue
            partes = linha.replace(";", ",").split(",")
            if len(partes) < 5:
                print(f"  [AVISO] Linha {n_linha} ignorada (formato inválido): {linha}")
                continue
            try:
                p   = partes[0].strip()
                x   = float(partes[1].strip())
                y   = float(partes[2].strip())
                z   = float(partes[3].strip())
                cod = partes[4].strip().upper()
                pontos.append({"p": p, "x": x, "y": y, "z": z, "cod": cod})
            except ValueError:
                print(f"  [AVISO] Linha {n_linha} ignorada (erro numérico): {linha}")
    print(f"  {len(pontos)} pontos lidos.")
    return pontos


def garantir_layer(doc, nome, cor):
    """Cria layer no DXF se ainda não existir"""
    if nome not in doc.layers:
        doc.layers.add(name=nome, color=cor)


def desenhar_linhas(msp, doc, pontos_por_cod):
    """Liga pontos do mesmo código numa polyline 3D"""
    for cod, pts in pontos_por_cod.items():
        info = CODIGOS.get(cod)
        if info is None:
            continue
        if "linha" not in info["tipo"]:
            continue
        if len(pts) < 2:
            print(f"  [INFO] Código {cod}: só 1 ponto, linha não gerada.")
            continue
        garantir_layer(doc, info["layer"], info["cor"])
        vertices = [(p["x"], p["y"], p["z"]) for p in pts]
        msp.add_polyline3d(
            vertices,
            dxfattribs={"layer": info["layer"], "color": info["cor"]},
        )
        print(f"  Linha [{cod}] — {len(pts)} pontos → layer '{info['layer']}'")


def desenhar_simbolos(msp, doc, pontos_por_cod):
    """Desenha círculo + texto com código e cota para símbolos"""
    for cod, pts in pontos_por_cod.items():
        info = CODIGOS.get(cod)

        if info is None:
            # Código desconhecido → coloca na layer DESCONHECIDO
            garantir_layer(doc, "DESCONHECIDO", 7)
            for p in pts:
                msp.add_circle(
                    (p["x"], p["y"]), RAIO_SIMBOLO,
                    dxfattribs={"layer": "DESCONHECIDO"},
                )
                msp.add_text(
                    f"{p['cod']} ({p['z']:.2f})",
                    dxfattribs={"layer": "DESCONHECIDO", "height": RAIO_SIMBOLO * 0.8},
                ).set_placement((p["x"] + RAIO_SIMBOLO * 1.2, p["y"]))
            continue

        if "simbolo" not in info["tipo"]:
            continue

        garantir_layer(doc, info["layer"], info["cor"])
        for p in pts:
            msp.add_circle(
                (p["x"], p["y"]), RAIO_SIMBOLO,
                dxfattribs={"layer": info["layer"], "color": info["cor"]},
            )
            msp.add_text(
                f"{cod} z={p['z']:.2f}",
                dxfattribs={
                    "layer":  info["layer"],
                    "color":  info["cor"],
                    "height": RAIO_SIMBOLO * 0.8,
                },
            ).set_placement((p["x"] + RAIO_SIMBOLO * 1.2, p["y"]))
        print(f"  Símbolo [{cod}] — {len(pts)} pontos → layer '{info['layer']}'")


def desenhar_curvas(msp, doc, todos_pontos):
    """Gera curvas de nível por interpolação TIN"""
    if len(todos_pontos) < 4:
        print("  [AVISO] Pontos insuficientes para curvas de nível (mín. 4).")
        return

    xs = np.array([p["x"] for p in todos_pontos])
    ys = np.array([p["y"] for p in todos_pontos])
    zs = np.array([p["z"] for p in todos_pontos])

    # Grelha de interpolação
    margem = 1.0
    xi = np.linspace(xs.min() - margem, xs.max() + margem, 300)
    yi = np.linspace(ys.min() - margem, ys.max() + margem, 300)
    XI, YI = np.meshgrid(xi, yi)

    interp = LinearNDInterpolator(list(zip(xs, ys)), zs)
    ZI = interp(XI, YI)

    z_min = np.ceil(zs.min() / INTERVALO_CURVAS) * INTERVALO_CURVAS
    z_max = np.floor(zs.max() / INTERVALO_CURVAS) * INTERVALO_CURVAS
    niveis = np.arange(z_min, z_max + INTERVALO_CURVAS * 0.5, INTERVALO_CURVAS)

    if len(niveis) == 0:
        print("  [AVISO] Sem variação de cota suficiente para curvas.")
        return

    # Usa matplotlib só para extrair as polilinhas das curvas
    fig, ax = plt.subplots()
    cs = ax.contour(XI, YI, ZI, levels=niveis)
    plt.close(fig)

    garantir_layer(doc, LAYER_CURVAS,        COR_CURVAS)
    garantir_layer(doc, LAYER_CURVAS_MESTRA, COR_CURVAS_MESTRA)

    # Compatibilidade matplotlib antigo (collections) e moderno (allsegs/get_paths)
    n_curvas = 0
    if hasattr(cs, "collections"):
        # API antiga
        iterador = zip(cs.collections, cs.levels)
        for col, nivel in iterador:
            mestra = abs(nivel % INTERVALO_MESTRAS) < 1e-6
            layer  = LAYER_CURVAS_MESTRA if mestra else LAYER_CURVAS
            cor    = COR_CURVAS_MESTRA   if mestra else COR_CURVAS
            for path in col.get_paths():
                verts = path.vertices
                if len(verts) < 2:
                    continue
                pts3d = [(float(v[0]), float(v[1]), float(nivel)) for v in verts]
                msp.add_polyline3d(pts3d, dxfattribs={"layer": layer, "color": cor})
                n_curvas += 1
    else:
        # API nova (matplotlib >= 3.8) — usa allsegs
        for nivel, segmentos in zip(cs.levels, cs.allsegs):
            mestra = abs(nivel % INTERVALO_MESTRAS) < 1e-6
            layer  = LAYER_CURVAS_MESTRA if mestra else LAYER_CURVAS
            cor    = COR_CURVAS_MESTRA   if mestra else COR_CURVAS
            for seg in segmentos:
                if len(seg) < 2:
                    continue
                pts3d = [(float(v[0]), float(v[1]), float(nivel)) for v in seg]
                msp.add_polyline3d(pts3d, dxfattribs={"layer": layer, "color": cor})
                n_curvas += 1

    print(
        f"  Curvas de nível: {n_curvas} polilinhas geradas "
        f"(intervalo {INTERVALO_CURVAS}m, mestras cada {INTERVALO_MESTRAS}m)"
    )


def adicionar_pontos_cotados(msp, doc, todos_pontos):
    """Adiciona número do ponto e cota a todos os pontos"""
    garantir_layer(doc, "PONTOS_NUM", 7)
    for p in todos_pontos:
        # Ponto (bolinha pequena)
        msp.add_circle(
            (p["x"], p["y"]), RAIO_SIMBOLO * 0.15,
            dxfattribs={"layer": "PONTOS_NUM", "color": 7},
        )
        # Número do ponto
        msp.add_text(
            str(p["p"]),
            dxfattribs={
                "layer":  "PONTOS_NUM",
                "color":  7,
                "height": RAIO_SIMBOLO * 0.6,
            },
        ).set_placement((
            p["x"] + RAIO_SIMBOLO * 0.3,
            p["y"] + RAIO_SIMBOLO * 0.3,
        ))
        # Cota
        msp.add_text(
            f"{p['z']:.3f}",
            dxfattribs={
                "layer":  "PONTOS_NUM",
                "color":  252,
                "height": RAIO_SIMBOLO * 0.6,
            },
        ).set_placement((
            p["x"] + RAIO_SIMBOLO * 0.3,
            p["y"] - RAIO_SIMBOLO * 0.8,
        ))


# =============================================================
# MAIN
# =============================================================

def main():
    if len(sys.argv) < 3:
        print("Uso:     python topo_field2finish.py <pontos.txt> <resultado.dxf>")
        print("Exemplo: python topo_field2finish.py levantamento.txt desenho.dxf")
        sys.exit(1)

    ficheiro_txt = sys.argv[1]
    ficheiro_dxf = sys.argv[2]

    print(f"\n{'='*55}")
    print(f"  TOPO FIELD2FINISH — MStopografia")
    print(f"  Entrada : {ficheiro_txt}")
    print(f"  Saída   : {ficheiro_dxf}")
    print(f"{'='*55}")

    # Ler pontos
    print("\n[1/4] A ler pontos...")
    pontos = ler_pontos(ficheiro_txt)
    if not pontos:
        print("Nenhum ponto válido encontrado. Verifica o ficheiro.")
        sys.exit(1)

    # Agrupar por código
    pontos_por_cod = {}
    for p in pontos:
        pontos_por_cod.setdefault(p["cod"], []).append(p)
    print(f"  Códigos encontrados: {list(pontos_por_cod.keys())}")

    # Criar DXF
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # Desenhar
    print("\n[2/4] A desenhar linhas...")
    desenhar_linhas(msp, doc, pontos_por_cod)

    print("\n[3/4] A desenhar símbolos...")
    desenhar_simbolos(msp, doc, pontos_por_cod)

    print("\n[4/4] A gerar curvas de nível...")
    desenhar_curvas(msp, doc, pontos)

    # Pontos numerados (todos)
    adicionar_pontos_cotados(msp, doc, pontos)

    # Guardar
    doc.saveas(ficheiro_dxf)
    print(f"\n  ✅ DXF gerado com sucesso: {ficheiro_dxf}")
    print(f"  Abre no AutoCAD/Civil 3D e usa ZOOM EXTENTS (Z → Enter → E → Enter)")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
