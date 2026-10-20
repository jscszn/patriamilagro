"""Imprime en consola el ID de cada botón, eje y hat que se presione en el control.

Uso: python tools/probar_control.py   (Ctrl+C o cerrar la ventana para salir)
Anota los IDs y ponlos en config/gamepad.json, o usa Opciones > Configurar control.
"""
import pygame

UMBRAL = 0.5


def main():
    pygame.init()
    pantalla = pygame.display.set_mode((420, 120))
    pygame.display.set_caption("Probar control - mira la consola")
    fuente = pygame.font.Font(None, 22)
    pantalla.blit(fuente.render("Presiona botones del control; los IDs salen en consola.",
                                True, (255, 255, 255)), (10, 50))
    pygame.display.flip()
    joysticks = {}
    ejes_activos = {}  # (instancia, eje) -> dirección, para no imprimir ruido
    print("Esperando controles... (conecta uno si no aparece)")
    reloj = pygame.time.Clock()
    try:
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return
                if e.type == pygame.JOYDEVICEADDED:
                    joy = pygame.joystick.Joystick(e.device_index)
                    joysticks[joy.get_instance_id()] = joy
                    print(f"CONECTADO: '{joy.get_name()}'  botones={joy.get_numbuttons()} "
                          f"ejes={joy.get_numaxes()} hats={joy.get_numhats()}")
                elif e.type == pygame.JOYDEVICEREMOVED:
                    joysticks.pop(e.instance_id, None)
                    print("DESCONECTADO")
                elif e.type == pygame.JOYBUTTONDOWN:
                    print(f"BOTON  id={e.button}  (presionado)")
                elif e.type == pygame.JOYBUTTONUP:
                    print(f"BOTON  id={e.button}  (soltado)")
                elif e.type == pygame.JOYHATMOTION:
                    print(f"HAT    id={e.hat}  valor={e.value}")
                elif e.type == pygame.JOYAXISMOTION:
                    direccion = -1 if e.value <= -UMBRAL else (1 if e.value >= UMBRAL else 0)
                    clave = (e.instance_id, e.axis)
                    if ejes_activos.get(clave, 0) != direccion:
                        ejes_activos[clave] = direccion
                        print(f"EJE    id={e.axis}  valor={e.value:+.2f}")
            reloj.tick(60)
    except KeyboardInterrupt:
        pass
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
