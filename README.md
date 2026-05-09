# MStopografia

> **Field to Finish automático** — converte ficheiros TXT de levantamento topográfico em DXF prontos para AutoCAD e Civil 3D.

## O problema

Um topógrafo profissional perde **2 a 4 horas por levantamento** a converter manualmente pontos de campo em desenho CAD.

## A solução

Três passos:

1. **Upload** do ficheiro TXT exportado da estação total ou GPS (`P,X,Y,Z,Código`)
2. **Configuração** dos códigos de campo (uma única vez)
3. **Download** do DXF completo com layers, símbolos e curvas de nível

O que demorava horas passa a demorar segundos.

## Funcionalidades

- ✅ Leitura de ficheiros TXT no formato `P,X,Y,Z,Código`
- ✅ Geração automática de polylines 3D por código
- ✅ Símbolos (círculo + texto) para pontos isolados
- ✅ Curvas de nível e curvas mestras por triangulação TIN
- ✅ Numeração e cotagem automática de todos os pontos
- ✅ Saída em DXF R2010 — compatível com AutoCAD, Civil 3D e BricsCAD

## Stack técnico

- **Backend:** Python 3.9+, ezdxf, numpy, scipy, matplotlib
- **Frontend:** HTML / CSS / JavaScript
- **Tipografia:** DM Sans + DM Mono
- **Cor de marca:** `#f0c040`

## Sobre

Construído por **Mário Sousa**, Product Specialist na Detalhe Virtual — empresa portuguesa de equipamentos de topografia.

Conhecimento direto do mercado: estações totais, GNSS, drones e LiDAR.

---

*Feito em Portugal 🇵🇹 — por um topógrafo, para topógrafos.*
