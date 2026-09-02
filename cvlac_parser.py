import requests
import re
import pandas as pd
from bs4 import BeautifulSoup





def cargar_cvlac(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    response.encoding = "ISO-8859-1"
    return BeautifulSoup(response.text, "html.parser")


def obtener_tabla_seccion(soup, nombre):
    encabezado = soup.find(
        lambda tag:
            tag.name in ["h1", "h2", "h3", "h4", "h5"]
            and tag.get_text(" ", strip=True).lower() == nombre.lower()
    )

    if not encabezado:
        return None

    return encabezado.find_parent("table")
    
    
    
#############################################################################################################


def extraer_formacion_academica(soup):
    tabla = obtener_tabla_seccion(soup, "Formación Académica")

    if tabla is None:
        return []

    registros = []

    filas = tabla.find_all("tr")

    # La primera fila contiene el encabezado
    for fila in filas[1:]:
        celdas = fila.find_all("td")

        if len(celdas) < 2:
            continue

        contenido = celdas[1]

        # El nivel está dentro de <b>
        nivel_tag = contenido.find("b")
        nivel = nivel_tag.get_text(" ", strip=True) if nivel_tag else ""

        # Extraemos el texto separado por <br>
        partes = list(contenido.stripped_strings)

        # Eliminamos el nivel, que ya lo tenemos
        partes = [
            p for p in partes
            if p != nivel
        ]

        registros.append({
            "nivel": nivel,
            "institucion": partes[0] if len(partes) > 0 else "",
            "programa": partes[1] if len(partes) > 1 else "",
            "periodo": partes[2] if len(partes) > 2 else "",
            "trabajo_grado": partes[3] if len(partes) > 3 else "",
        })

    return registros



        
def inspeccionar_seccion(soup, nombre, limite=3):
    tabla = obtener_tabla_seccion(soup, nombre)

    if tabla is None:
        print(f"No se encontró: {nombre}")
        return

    print(f"\n{'=' * 70}")
    print(f"SECCIÓN: {nombre}")
    print(f"{'=' * 70}")

    filas = tabla.find_all("tr")

    for i, fila in enumerate(filas[:limite]):
        print(f"\n--- FILA {i} ---")
        print(fila.get_text(" | ", strip=True))
        print("\nHTML:")
        print(fila.prettify()[:5000])
        

def inspeccionar_articulos(soup):
    tabla = obtener_tabla_seccion(soup, "Artículos")

    if tabla is None:
        print("No se encontró la sección Artículos")
        return

    blockquotes = tabla.find_all("blockquote")

    print(f"Artículos encontrados: {len(blockquotes)}")

    for i, articulo in enumerate(blockquotes[:5], 1):
        print("\n" + "=" * 70)
        print(f"ARTÍCULO {i}")
        print("=" * 70)

        print(articulo.get_text(" ", strip=True))
        


def inspeccionar_articulo_html(soup, numero=1):
    tabla = obtener_tabla_seccion(soup, "Artículos")

    if tabla is None:
        print("No se encontró la sección Artículos")
        return

    articulos = tabla.find_all("blockquote")

    if numero > len(articulos):
        print("Número de artículo fuera de rango")
        return

    articulo = articulos[numero - 1]

    print("=" * 70)
    print(f"ESTRUCTURA DEL ARTÍCULO {numero}")
    print("=" * 70)

    for i, nodo in enumerate(articulo.contents):
        if getattr(nodo, "name", None):
            print(f"\nNODO {i} → <{nodo.name}>")
            print(repr(nodo.get_text(" ", strip=True)))
        else:
            texto = str(nodo).strip()
            if texto:
                print(f"\nNODO {i} → TEXTO")
                print(repr(texto))


def extraer_autores_titulo(texto):
    """
    Extrae autores y título del primer bloque de un artículo CvLAC.
    """

    # Limpiar espacios y saltos de línea
    texto = re.sub(r"\s+", " ", texto).strip()

    # Separar antes de ". En:"
    if ". En:" not in texto:
        return [], ""

    parte_principal = texto.split(". En:", 1)[0].strip()

    # El título está entre comillas
    coincidencia = re.search(r'"([^"]+)"', parte_principal)

    if not coincidencia:
        return [], parte_principal

    titulo = coincidencia.group(1).strip()

    # Todo lo anterior al título corresponde a autores
    autores_texto = parte_principal[:coincidencia.start()].strip()

    # Separar por comas
    autores = [
        autor.strip()
        for autor in autores_texto.split(",")
        if autor.strip()
    ]

    return autores, titulo
    
def probar_autores_titulo(soup):
    tabla = obtener_tabla_seccion(soup, "Artículos")
    articulos = tabla.find_all("blockquote")

    articulo = articulos[0]

    # El primer nodo de texto
    texto = articulo.contents[0].get_text(" ", strip=True) \
        if hasattr(articulo.contents[0], "get_text") \
        else str(articulo.contents[0])

    autores, titulo = extraer_autores_titulo(texto)

    print("\nAUTORES:")
    for autor in autores:
        print(f"  - {autor}")

    print("\nTÍTULO:")
    print(titulo)
    
    
def extraer_datos_articulo(articulo):
    """
    Extrae información bibliográfica de un <blockquote> de CvLAC.
    """

    texto = articulo.get_text(" ", strip=True)

    # Normalizar espacios
    texto = re.sub(r"\s+", " ", texto).strip()

    autores, titulo = extraer_autores_titulo(texto)

    datos = {
        "autores": autores,
        "titulo": titulo,
        "revista": "",
        "issn": "",
        "editorial": "",
        "volumen": "",
        "fasciculo": "",
        "paginas": "",
        "anio": "",
        "doi": "",
    }


    # ---------------------------------------------------------
    # Revista
    # ---------------------------------------------------------

    match = re.search(r'En:\s*(.+?)\s+ISSN:', texto)

    if match:
        datos["revista"] = match.group(1).strip()

    # ---------------------------------------------------------
    # ISSN
    # ---------------------------------------------------------

    match = re.search(r'ISSN:\s*([0-9Xx-]+)', texto)

    if match:
            datos["issn"] = normalizar_issn(match.group(1))

    # ---------------------------------------------------------
    # Editorial
    # ---------------------------------------------------------

    match = re.search(r'ed:\s*(.+?)\s+v\.', texto)

    if match:
        datos["editorial"] = match.group(1).strip()

    # ---------------------------------------------------------
    # Volumen
    # ---------------------------------------------------------

    match = re.search(r'\bv\.\s*([^\s]+)', texto)

    if match:
        datos["volumen"] = match.group(1).strip()

    # ---------------------------------------------------------
    # Fascículo
    # ---------------------------------------------------------

    match = re.search(r'fasc\.\s*([^\s]+)', texto)

    if match:
        datos["fasciculo"] = match.group(1).strip()

    # ---------------------------------------------------------
    # Páginas
    # ---------------------------------------------------------

    match = re.search(
        r'p\.\s*([0-9]+)\s*-\s*([0-9]+)',
        texto
    )

    if match:
        datos["paginas"] = f"{match.group(1)}-{match.group(2)}"

    # ---------------------------------------------------------
    # Año
    # ---------------------------------------------------------

    match = re.search(
        r',\s*(\d{4}),\s*DOI:',
        texto
    )

    if match:
        datos["anio"] = int(match.group(1))

    # ---------------------------------------------------------
    # DOI
    # ---------------------------------------------------------

    match = re.search(
        r'DOI:\s*(10\.\d{4,9}/[-._;()/:A-Z0-9]+)',
        texto,
        re.IGNORECASE
    )

    if match:
        datos["doi"] = match.group(1).strip()

    return datos
    

import pandas as pd


def articulos_a_dataframe(soup):
    tabla = obtener_tabla_seccion(soup, "Artículos")

    if tabla is None:
        return pd.DataFrame()

    articulos = tabla.find_all("blockquote")

    registros = []

    for articulo in articulos:
        datos = extraer_datos_articulo(articulo)

        autores = datos["autores"]

        datos["autores_texto"] = "; ".join(autores)
        datos["n_autores"] = len(autores)

        datos["primer_autor"] = autores[0] if autores else ""
        datos["ultimo_autor"] = autores[-1] if autores else ""

        registros.append(datos)

    return pd.DataFrame(registros)
    
    
def normalizar_issn(issn):
    if not issn:
        return ""

    # Dejar únicamente números y X
    issn = re.sub(r"[^0-9Xx]", "", issn).upper()

    # Formato XXXX-XXXX
    if len(issn) == 8:
        return issn[:4] + "-" + issn[4:]

    return issn
##################################################################################################    
    
    
def extraer_eventos_cientificos(soup):

    tabla = obtener_tabla_seccion(soup, "Eventos científicos")

    if tabla is None:
        return pd.DataFrame()

    filas_resultado = []

    tablas_eventos = tabla.find_all("table")

    for tabla_evento in tablas_eventos:

        texto = tabla_evento.get_text(" ", strip=True)

        # ---------------------------------------------------------
        # Datos generales del evento
        # ---------------------------------------------------------

        nombre_evento = ""

        match = re.search(
            r"Nombre del evento:\s*(.+?)\s*Tipo de evento:",
            texto
        )

        if match:
            nombre_evento = match.group(1).strip()


        tipo_evento = ""

        match = re.search(
            r"Tipo de evento:\s*(.+?)\s*Ámbito:",
            texto
        )

        if match:
            tipo_evento = match.group(1).strip()


        ambito = ""

        match = re.search(
            r"Ámbito:\s*(.+?)\s*Realizado el:",
            texto
        )

        if match:
            ambito = match.group(1).strip()


        fecha = ""
        lugar = ""

        match = re.search(
            r"Realizado el:(\d{4}-\d{2}-\d{2}).*?"
            r"\s+en\s+(.+?)(?=\s+Productos asociados|\s+Instituciones asociadas|\s+Participantes|$)",
            texto
        )

        if match:
            fecha = match.group(1).strip()
            lugar = match.group(2).strip()


        # ---------------------------------------------------------
        # Institución
        # ---------------------------------------------------------

        institucion = ""
        tipo_vinculacion = ""

        match = re.search(
            r"Nombre de la institución:\s*(.+?)\s*"
            r"Tipo de vinculación\s*(.+?)(?=\s+Participantes|$)",
            texto
        )

        if match:
            institucion = match.group(1).strip()
            tipo_vinculacion = match.group(2).strip()


        # ---------------------------------------------------------
        # Productos asociados
        # ---------------------------------------------------------

        productos = []

        for li in tabla_evento.find_all("li"):

            li_texto = li.get_text(" ", strip=True)

            if "Nombre del producto:" not in li_texto:
                continue

            nombre_producto = ""
            tipo_producto = ""

            match = re.search(
                r"Nombre del producto:\s*(.+?)\s*"
                r"Tipo de producto:",
                li_texto
            )

            if match:
                nombre_producto = match.group(1).strip()

            match = re.search(
                r"Tipo de producto:\s*(.+)",
                li_texto
            )

            if match:
                tipo_producto = match.group(1).strip()

            productos.append({
                "producto": nombre_producto,
                "tipo_producto": tipo_producto
            })


        # ---------------------------------------------------------
        # Participantes
        # ---------------------------------------------------------

        participantes = []

        for li in tabla_evento.find_all("li"):

            li_texto = li.get_text(" ", strip=True)

            if "Rol en el evento:" not in li_texto:
                continue

            match = re.search(
                r"Nombre:\s*(.+?)\s+Rol en el evento:\s*(.+)",
                li_texto
            )

            if match:

                participantes.append({
                    "participante": match.group(1).strip(),
                    "rol": match.group(2).strip()
                })


        # ---------------------------------------------------------
        # Crear filas
        # ---------------------------------------------------------

        if not participantes:
            participantes = [{
                "participante": "",
                "rol": ""
            }]

        if not productos:
            productos = [{
                "producto": "",
                "tipo_producto": ""
            }]


        for participante in participantes:

            for producto in productos:

                filas_resultado.append({
                    "nombre_evento": nombre_evento,
                    "tipo_evento": tipo_evento,
                    "ambito": ambito,
                    "fecha": fecha,
                    "lugar": lugar,
                    "institucion": institucion,
                    "tipo_vinculacion": tipo_vinculacion,
                    "producto": producto["producto"],
                    "tipo_producto": producto["tipo_producto"],
                    "participante": participante["participante"],
                    "rol": participante["rol"]
                })


    return pd.DataFrame(filas_resultado)

def inspeccionar_trabajo_html(soup, numero=1):

    tabla = obtener_tabla_seccion(
        soup,
        "Trabajos dirigidos/tutorías"
    )

    trabajos = tabla.find_all("blockquote")

    if numero > len(trabajos):
        print("Número de trabajo fuera de rango")
        return

    trabajo = trabajos[numero - 1]

    print("=" * 70)
    print(f"TRABAJO {numero}")
    print("=" * 70)

    print(work := trabajo.prettify())
 
 
 
 
 
 
def extraer_trabajos_dirigidos(soup):

    tabla = obtener_tabla_seccion(
        soup,
        "Trabajos dirigidos/tutorías"
    )

    if tabla is None:
        return pd.DataFrame()

    registros = []

    # Recorremos las categorías de trabajos
    filas = tabla.find_all("tr")

    tipo_trabajo = ""

    for fila in filas:

        # ---------------------------------------------------------
        # Identificar categoría
        # ---------------------------------------------------------

        li = fila.find("li")

        if li:
            texto_categoria = li.get_text(" ", strip=True)

            if texto_categoria.startswith("Trabajos dirigidos/Tutorías -"):
                tipo_trabajo = texto_categoria.replace(
                    "Trabajos dirigidos/Tutorías -",
                    ""
                ).strip()

                continue

        # ---------------------------------------------------------
        # Identificar trabajo
        # ---------------------------------------------------------

        blockquote = fila.find("blockquote")

        if not blockquote:
            continue

        partes = list(blockquote.stripped_strings)

        if len(partes) < 4:
            continue

        # ---------------------------------------------------------
        # PRIMER BLOQUE
        #
        # Contiene:
        # autor
        # título
        # institución
        # Estado + programa + año
        # ---------------------------------------------------------

        primera_parte = partes[0]

        # Conservamos los saltos de línea originales
        lineas = [
            re.sub(r"\s+", " ", linea).strip(" ,")
            for linea in re.split(r"\r?\n", primera_parte)
            if linea.strip()
        ]

        # Normalmente:
        # 0 = autor
        # 1 = título
        # 2 = institución
        # 3 = Estado...
        if len(lineas) < 4:
            continue

        titulo = lineas[1]
        institucion = lineas[2]
        estado_programa_anio = " ".join(lineas[3:])

        # ---------------------------------------------------------
        # Estado, programa y año
        # ---------------------------------------------------------

        estado = ""
        programa = ""
        anio = ""

        match = re.search(
            r"Estado:\s*(.*?),?\s*(\d{4})\s*\.$",
            estado_programa_anio
        )

        if match:

            bloque_estado_programa = match.group(1).strip()
            anio = int(match.group(2))

            # Estados conocidos de CvLAC
            estados_conocidos = [
                "Tesis concluida",
                "Tesis en curso",
                "Trabajo de grado concluido",
                "Trabajo de grado en curso",
                "Monografía concluida",
                "Monografía en curso"
            ]

            estado = ""
            programa = bloque_estado_programa

            for estado_posible in estados_conocidos:

                if bloque_estado_programa.startswith(estado_posible):
                    estado = estado_posible
                    programa = bloque_estado_programa[
                        len(estado_posible):
                    ].strip(" ,")
                    break

        # ---------------------------------------------------------
        # Tipo de orientación
        # ---------------------------------------------------------

        tipo_orientacion = ""

        for i, parte in enumerate(partes):

            if parte == "Dirigió como:" and i + 1 < len(partes):
                tipo_orientacion = partes[i + 1].strip(" ,")
                break

        # ---------------------------------------------------------
        # Personas orientadas y tutores/cotutores
        # ---------------------------------------------------------

        persona_orientada = ""
        tutores_cotutores = ""

        for i, parte in enumerate(partes):

            if parte == "Persona(s) orientada(s):":

                if i + 1 < len(partes):

                    bloque_personas = partes[i + 1]

                    if "Tutor(es)/Cotutor(es):" in bloque_personas:

                        personas, tutores = bloque_personas.split(
                            "Tutor(es)/Cotutor(es):",
                            1
                        )

                        persona_orientada = personas.strip(" ,")
                        tutores_cotutores = tutores.strip(" ,")

                    else:
                        persona_orientada = bloque_personas.strip(" ,")

                break

        # ---------------------------------------------------------
        # Áreas
        # ---------------------------------------------------------

        areas = ""

        for i, parte in enumerate(partes):

            if parte == "Areas:" and i + 1 < len(partes):
                areas = partes[i + 1].strip(" ,")
                break

        # ---------------------------------------------------------
        # Separar personas orientadas
        # ---------------------------------------------------------

        personas = [
            p.strip()
            for p in re.split(r"\r?\n+", persona_orientada)
            if p.strip()
        ]

        # Si por alguna razón no se pudieron separar,
        # conservamos una sola persona
        if not personas:
            personas = [""]

        # ---------------------------------------------------------
        # UNA FILA POR PERSONA ORIENTADA
        # ---------------------------------------------------------

        for persona in personas:

            registros.append({
                "tipo_trabajo": tipo_trabajo,
                "titulo": titulo,
                "institucion": institucion,
                "estado": estado,
                "programa": programa,
                "anio": anio,
                "tipo_orientacion": tipo_orientacion,
                "persona_orientada": persona,
                "tutores_cotutores": tutores_cotutores,
                "areas": areas
            })

    return pd.DataFrame(registros) 
 
def extraer_obras_productos(soup):
    tabla = obtener_tabla_seccion(soup, "Obras o productos")

    if tabla is None:
        return pd.DataFrame()

    productos = tabla.find_all("blockquote")

    registros = []

    for producto in productos:

        datos = {
            "nombre_producto": "",
            "disciplina": "",
            "fecha_creacion": "",
            "espacio_evento": "",
            "fecha_presentacion": "",
            "entidad_convocante": "",
        }

        # ---------------------------------------------------------
        # Datos principales de la obra/producto
        # ---------------------------------------------------------

        texto = producto.get_text(" ", strip=True)
        texto = re.sub(r"\s+", " ", texto).strip()

        match = re.search(
            r"Nombre del producto:\s*(.*?)\s*,?\s*Disciplina:",
            texto,
            re.IGNORECASE
        )

        if match:
            datos["nombre_producto"] = match.group(1).strip(" ,")

        match = re.search(
            r"Disciplina:\s*(.*?)\s*,?\s*Fecha de creación:",
            texto,
            re.IGNORECASE
        )

        if match:
            datos["disciplina"] = match.group(1).strip(" ,")

        match = re.search(
            r"Fecha de creación:\s*(.*?)(?:\s*INSTANCIAS DE VALORACIÓN|\s*$)",
            texto,
            re.IGNORECASE
        )

        if match:
            datos["fecha_creacion"] = match.group(1).strip(" ,")

        # ---------------------------------------------------------
        # Instancia de valoración
        # ---------------------------------------------------------

        match = re.search(
            r"Nombre del espacio o evento:\s*(.*?),\s*"
            r"Fecha de presentación:",
            texto,
            re.IGNORECASE
        )

        if match:
            datos["espacio_evento"] = match.group(1).strip(" ,")

        match = re.search(
            r"Fecha de presentación:\s*(.*?),\s*"
            r"Entidad convocante",
            texto,
            re.IGNORECASE
        )

        if match:
            datos["fecha_presentacion"] = match.group(1).strip(" ,")

        match = re.search(
            r"Entidad convocante 1:\s*(.*?)(?:\s*$)",
            texto,
            re.IGNORECASE
        )

        if match:
            datos["entidad_convocante"] = match.group(1).strip(" ,")

        registros.append(datos)

    return pd.DataFrame(registros)
 
 
def extraer_proyectos(soup):
    tabla = obtener_tabla_seccion(soup, "Proyectos")

    if tabla is None:
        return []

    registros = []

    for proyecto in tabla.find_all("blockquote"):
        # Tipo de proyecto
        tipo_tag = proyecto.find("i", string=lambda s: s and "Tipo de proyecto:" in s)
        tipo_proyecto = ""

        if tipo_tag:
            tipo_proyecto = tipo_tag.next_sibling
            if tipo_proyecto:
                tipo_proyecto = tipo_proyecto.strip()

        # Texto completo
        texto = proyecto.get_text(" ", strip=True)

        # Título
        titulo = ""
        if tipo_tag:
            br = tipo_tag.find_next("br")
            if br:
                siguiente = br.find_next_sibling(string=True)
                if siguiente:
                    titulo = siguiente.strip()

        # Inicio
        inicio = ""
        inicio_tag = proyecto.find("i", string=lambda s: s and "Inicio:" in s)
        if inicio_tag:
            partes = []
            nodo = inicio_tag.next_sibling

            while nodo and getattr(nodo, "name", None) != "i":
                if isinstance(nodo, str):
                    partes.append(nodo.strip())
                nodo = nodo.next_sibling

            inicio = " ".join(p for p in partes if p)

        # Fin
        fin = ""
        fin_tag = proyecto.find("i", string=lambda s: s and "Fin:" in s)
        if fin_tag:
            partes = []
            nodo = fin_tag.next_sibling

            while nodo and getattr(nodo, "name", None) != "i":
                if isinstance(nodo, str):
                    partes.append(nodo.strip())
                nodo = nodo.next_sibling

            fin = " ".join(p for p in partes if p)

        # Resumen
        resumen = ""
        resumen_tag = proyecto.find("b", string=lambda s: s and "Resumen" in s)

        if resumen_tag:
            parrafo = resumen_tag.find_next("p")
            if parrafo:
                resumen = parrafo.get_text(" ", strip=True)

        registros.append({
            "tipo_proyecto": tipo_proyecto,
            "titulo": titulo,
            "inicio": inicio,
            "fin": fin,
            "resumen": resumen
        })

    return registros
    
"""    
if __name__ == "__main__":
    soup = cargar_cvlac(URL)

    df_articulos = articulos_a_dataframe(soup)

    print("\n")
    print("=" * 70)
    print("DATAFRAME DE ARTÍCULOS")
    print("=" * 70)

    print(df_articulos.to_string(index=False))
    """