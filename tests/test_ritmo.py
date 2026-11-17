"""Ritmo de los cuadros: un paso de simulación por imagen (sin saltos dobles ni cuadros repetidos)."""
import unittest

import settings
from ritmo import Ritmo, ajustar


class RelojFalso:
    """Reloj de mentira: dormir se pasa de largo un 25 %, como en macOS."""

    def __init__(self, exceso: float = 1.25):
        self.t = 100.0
        self.exceso = exceso

    def reloj(self) -> float:
        self.t += 0.00001                 # mirar el reloj también tarda un poco
        return self.t

    def dormir(self, segundos: float) -> None:
        self.t += segundos * self.exceso


class TestAjustar(unittest.TestCase):
    def test_el_temblor_del_reloj_cuenta_como_un_cuadro_exacto(self):
        for ms in (15.2, 16.0, 16.67, 17.0, 18.2, 20.0):
            self.assertEqual(ajustar(ms / 1000, settings.DT), settings.DT, ms)

    def test_un_cuadro_lento_de_verdad_no_se_disimula(self):
        for ms in (5.0, 8.3, 25.0, 33.3, 250.0):
            self.assertEqual(ajustar(ms / 1000, settings.DT), ms / 1000, ms)


class TestRitmo(unittest.TestCase):
    def cuadros(self, falso: RelojFalso, trabajo: float = 0.0015, n: int = 300):
        ritmo = Ritmo(settings.FPS, reloj=falso.reloj, dormir=falso.dormir)
        dts = []
        for _ in range(n):
            falso.t += trabajo            # lo que tarda el juego en simular y dibujar
            dts.append(ritmo.esperar())
        return dts

    def test_cada_cuadro_dura_un_sesentavo_aunque_dormir_se_pase(self):
        for exceso in (1.0, 1.25, 1.6):
            dts = self.cuadros(RelojFalso(exceso))
            self.assertAlmostEqual(sum(dts) / len(dts), settings.DT, delta=0.00002, msg=exceso)
            self.assertLess(max(abs(d - settings.DT) for d in dts), 0.0003, exceso)

    def test_un_paso_de_simulacion_por_cuadro(self):
        """Lo mismo que hace Juego.frame con el acumulador: nunca 0 ni 2 pasos."""
        acumulador, pasos = 0.0, []
        for dt in self.cuadros(RelojFalso(), n=600):
            acumulador += ajustar(dt, settings.DT)
            n = 0
            while acumulador >= settings.DT:
                acumulador -= settings.DT
                n += 1
            pasos.append(n)
        self.assertEqual(set(pasos), {1})

    def test_tras_un_cuadro_lento_no_acelera_para_recuperar(self):
        falso = RelojFalso()
        ritmo = Ritmo(settings.FPS, reloj=falso.reloj, dormir=falso.dormir)
        ritmo.esperar()
        falso.t += 0.2                    # un tirón de 200 ms (cargar una escena, arrastrar la ventana)
        self.assertGreater(ritmo.esperar(), 0.19)
        for _ in range(5):                # los siguientes vuelven al periodo normal, no más cortos
            self.assertAlmostEqual(ritmo.esperar(), settings.DT, delta=0.0003)


class TestWeb(unittest.TestCase):
    def test_medir_no_espera(self):
        """En la web el navegador marca los cuadros: medir() solo informa el tiempo pasado."""
        falso = RelojFalso()
        ritmo = Ritmo(settings.FPS, reloj=falso.reloj, dormir=falso.dormir)
        falso.t += 0.0167
        antes = falso.t
        self.assertAlmostEqual(ritmo.medir(), 0.0167, delta=0.0001)
        self.assertLess(falso.t - antes, 0.0001)             # no durmió ni se quedó esperando

    def test_atajos_en_la_direccion_de_la_pagina(self):
        from main import opciones_web
        nada = {"nivel": None, "arena": False}
        self.assertEqual(opciones_web("", "localhost"), nada)
        self.assertEqual(opciones_web("?nivel=3&arena=1", "localhost"), {"nivel": 3, "arena": True})
        self.assertEqual(opciones_web("?nivel=2", "127.0.0.1"), {"nivel": 2, "arena": False})
        self.assertEqual(opciones_web("?nivel=9&otra", "localhost"), nada)

    def test_en_la_pagina_publicada_los_atajos_no_hacen_nada(self):
        from main import opciones_web
        nada = {"nivel": None, "arena": False}
        for equipo in ("ejemplo.org", "www.ejemplo.org", "localhost.ejemplo.org", ""):
            self.assertEqual(opciones_web("?nivel=3&arena=1", equipo), nada, equipo)
        self.assertEqual(opciones_web("?nivel=3&arena=1"), nada)       # sin saber dónde corre: no

    def test_en_escritorio_no_es_web(self):
        self.assertFalse(settings.WEB)


if __name__ == "__main__":
    unittest.main()
