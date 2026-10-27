"""Static content compiled into the asset page: T9 dictionary (ES + EN), sample ebook."""
import os

EN = """the of and to in is you that it he was for on are as with his they at be this have from or one had by word but not what all were we when your can said there use an each which she do how their if will up other about out many then them these so some her would make like him into time has look two more write go see number no way could people my than first water been call who oil its now find long down day did get come made may part
hello hi yes ok thanks please sorry good bad great love like help what why where who when how today tomorrow now later wait stop start open close read write send call text name home work school food drink eat sleep play game music book movie phone friend family mother father brother sister child man woman boy girl world life city country street house room door table chair car bus train plane
calculator battery screen key math number plus minus times divide zero one two three four five six seven eight nine ten hundred thousand million derivative integral equation graph function solve simplify square root
weather news wiki search chat store download update system power energy low high fast slow big small new old hot cold red green blue black white""".split()

ES = """de la que el en y a los se del las un por con no una su para es al lo como mas pero sus le ya o este si porque esta entre cuando muy sin sobre tambien me hasta hay donde quien desde todo nos durante todos uno les ni contra otros ese eso ante ellos e esto mi antes algunos que unos yo otro otras otra el tanto esa estos mucho quienes nada muchos cual poco ella estar estas algunas algo nosotros
hola adios si gracias favor perdon bueno malo genial amor ayuda que porque donde quien cuando como hoy manana ahora luego espera para inicio abrir cerrar leer escribir enviar llamar texto nombre casa trabajo escuela comida bebida comer dormir jugar musica libro pelicula telefono amigo familia madre padre hermano hermana nino hombre mujer mundo vida ciudad pais calle cuarto puerta mesa silla auto
calculadora bateria pantalla tecla numero mas menos por entre cero uno dos tres cuatro cinco seis siete ocho nueve diez cien mil millon derivada integral ecuacion grafico funcion resolver simplificar cuadrado raiz
clima noticias wiki buscar chat tienda bajar actualizar sistema energia bajo alto rapido lento grande pequeno nuevo viejo caliente frio rojo verde azul negro blanco""".split()


def dictionary():
    seen = []
    for w in EN + ES:
        w = w.lower()
        if w.isalpha() and w not in seen and len(w) <= 12:
            seen.append(w)
    return ("\n".join(seen) + "\n\0").encode("ascii")


BOOK = """SUPER-OS
========

CAPITULO 1 / CHAPTER 1

La calculadora dormia. No el sueno superficial de un salvapantallas, sino
sueno de verdad: el LCD apagado, los timers en silencio, el reloj del Z80
detenido, esperando una tecla o un susurro por el cable.

Every wait in this system is a HALT. No loop spins. No cycle is wasted.
When you press a key the interrupt wakes the CPU, the scheduler runs the
one task that needs to run, and the processor goes back to sleep.

Texts and pictures are stored compressed with ZX0 and unpacked straight
into RAM in a few milliseconds. UP/DOWN scroll, CLEAR goes back.
""".encode("ascii")

ABOUT = b"Super-OS 0.1\nZ80 15MHz TI-83 Plus SE\n"


def demo():
    f = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build", "demo.bin")
    return open(f, "rb").read() if os.path.exists(f) else bytes([0xC9])


def files():
    return [("DEMO", demo()), ("DICT", dictionary()), ("BOOK1", BOOK + b"\0"), ("ABOUT", ABOUT + b"\0")]
