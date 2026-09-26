"""Reviewed Google Fonts files required by the pinned JIZURA source."""

SOURCE_COMMIT = "23e54b51ddffbc7713c583748e3bd86f62b1fa4a"


def family(name, slug, fonts, *, license_slug=None):
    return {
        "name": name,
        "slug": slug,
        "license_slug": license_slug or slug,
        "fonts": fonts,
    }


def font(filename, weight):
    return {"filename": filename, "weight": weight, "style": "normal"}


FAMILIES = [
    family("Noto Sans JP", "notosansjp", [font("NotoSansJP[wght].ttf", "100 900")]),
    family("Noto Serif JP", "notoserifjp", [font("NotoSerifJP[wght].ttf", "200 900")]),
    family("Dela Gothic One", "delagothicone", [font("DelaGothicOne-Regular.ttf", "400")]),
    family("Zen Kaku Gothic New", "zenkakugothicnew", [font("ZenKakuGothicNew-Black.ttf", "900")]),
    family("Zen Old Mincho", "zenoldmincho", [font("ZenOldMincho-Black.ttf", "900")]),
    family("Kaisei Tokumin", "kaiseitokumin", [font("KaiseiTokumin-ExtraBold.ttf", "800")]),
    family(
        "M PLUS Rounded 1c",
        "mplusrounded1c",
        [font("MPLUSRounded1c-ExtraBold.ttf", "800")],
        license_slug="roundedmplus1c",
    ),
    family("Mochiy Pop One", "mochiypopone", [font("MochiyPopOne-Regular.ttf", "400")]),
    family("DotGothic16", "dotgothic16", [font("DotGothic16-Regular.ttf", "400")]),
    family("Yuji Syuku", "yujisyuku", [font("YujiSyuku-Regular.ttf", "400")]),
    family(
        "IBM Plex Mono",
        "ibmplexmono",
        [font("IBMPlexMono-Medium.ttf", "500"), font("IBMPlexMono-SemiBold.ttf", "600")],
    ),
    family(
        "IBM Plex Sans JP",
        "ibmplexsansjp",
        [
            font("IBMPlexSansJP-Regular.ttf", "400"),
            font("IBMPlexSansJP-Medium.ttf", "500"),
            font("IBMPlexSansJP-Bold.ttf", "700"),
        ],
    ),
    family("Reggae One", "reggaeone", [font("ReggaeOne-Regular.ttf", "400")]),
    family("Rampart One", "rampartone", [font("RampartOne-Regular.ttf", "400")]),
    family("Potta One", "pottaone", [font("PottaOne-Regular.ttf", "400")]),
    family("Kiwi Maru", "kiwimaru", [font("KiwiMaru-Medium.ttf", "500")]),
    family("Klee One", "kleeone", [font("KleeOne-SemiBold.ttf", "600")]),
    family("Shippori Mincho B1", "shipporiminchob1", [font("ShipporiMinchoB1-ExtraBold.ttf", "800")]),
    family("Noto Sans TC", "notosanstc", [font("NotoSansTC[wght].ttf", "100 900")]),
    family("Noto Serif TC", "notoseriftc", [font("NotoSerifTC[wght].ttf", "200 900")]),
    family("WDXL Lubrifont TC", "wdxllubrifonttc", [font("WDXLLubrifontTC-Regular.ttf", "400")]),
    family("Chiron GoRound TC", "chirongoroundtc", [font("ChironGoRoundTC[wght].ttf", "200 900")]),
    family("Huninn", "huninn", [font("Huninn-Regular.ttf", "400")]),
    family("LXGW WenKai TC", "lxgwwenkaitc", [font("LXGWWenKaiTC-Bold.ttf", "700")]),
    family("LXGW Marker Gothic", "lxgwmarkergothic", [font("LXGWMarkerGothic-Regular.ttf", "400")]),
    family("Noto Sans SC", "notosanssc", [font("NotoSansSC[wght].ttf", "100 900")]),
    family("Noto Serif SC", "notoserifsc", [font("NotoSerifSC[wght].ttf", "200 900")]),
    family("ZCOOL QingKe HuangYou", "zcoolqingkehuangyou", [font("ZCOOLQingKeHuangYou-Regular.ttf", "400")]),
    family("ZCOOL KuaiLe", "zcoolkuaile", [font("ZCOOLKuaiLe-Regular.ttf", "400")]),
    family("ZCOOL XiaoWei", "zcoolxiaowei", [font("ZCOOLXiaoWei-Regular.ttf", "400")]),
    family("Ma Shan Zheng", "mashanzheng", [font("MaShanZheng-Regular.ttf", "400")]),
    family("Noto Sans KR", "notosanskr", [font("NotoSansKR[wght].ttf", "100 900")]),
    family("Noto Serif KR", "notoserifkr", [font("NotoSerifKR[wght].ttf", "200 900")]),
    family("IBM Plex Sans KR", "ibmplexsanskr", [font("IBMPlexSansKR-Medium.ttf", "500")]),
    family("Black Han Sans", "blackhansans", [font("BlackHanSans-Regular.ttf", "400")]),
    family("Jua", "jua", [font("Jua-Regular.ttf", "400")]),
    family("Do Hyeon", "dohyeon", [font("DoHyeon-Regular.ttf", "400")]),
    family("Gowun Dodum", "gowundodum", [font("GowunDodum-Regular.ttf", "400")]),
    family("Gowun Batang", "gowunbatang", [font("GowunBatang-Bold.ttf", "700")]),
    family("Nanum Brush Script", "nanumbrushscript", [font("NanumBrushScript-Regular.ttf", "400")]),
]
