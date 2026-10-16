#!/usr/bin/env python3
"""Extrae T media mensual por estación del documento oficial SMN 1991-2020.

Fuente: https://repositorio.smn.gob.ar/handle/20.500.12160/2506
Conserva "S/D" como null; NO es un campo climatológico en grilla.
"""
import argparse
import fitz
import hashlib
import json
import re
from pathlib import Path

PDF_URL="https://repositorio.smn.gob.ar/bitstream/handle/20.500.12160/2506/estad%C3%ADsticas_climatol%C3%B3gicas_normales_1991-2020.pdf?sequence=4"

def parse(pdf_path):
    path=Path(pdf_path)
    doc=fitz.open(path)
    if len(doc)<852:raise ValueError(f"Publicación incompleta: {len(doc)} páginas")
    stations=[]
    for index in range(105):
        pdf_page=12+8*index
        page=doc[pdf_page].get_text(sort=True)
        latline=next(line for line in page.splitlines() if 'Latitud:' in line)
        lonline=next(line for line in page.splitlines() if 'Longitud:' in line)
        name=latline.split('Latitud:')[0].strip()
        lat=-float(re.search(r'Latitud:\s*([0-9.]+)\s+Sur',latline).group(1))
        lon=-float(re.search(r'Longitud:\s*([0-9.]+)\s+Oeste',lonline).group(1))
        elevation=re.search(r'Altura Campo de Obs:\s*(\d+)\s+metros',latline)
        wigos=re.search(r'Identificador WIGOS:\s*(\S+)',latline)
        years=re.search(r'Período:\s*(\d{4}-\d{4})',lonline)
        section=page[page.index('Temperatura ('):page.index('Temperatura máxima')]
        line=re.search(r'(?m)^\s*Promedio\s+([^\n]+)',section)
        if not line:raise ValueError(f'No se pudo extraer la temperatura media: {name}')
        numbers=line.group(1).split()
        if len(numbers)!=13:raise ValueError(f'Temperaturas incompletas: {name}: {numbers}')
        vals=[None if value=='S/D' else float(value) for value in numbers]
        stations.append({
            'nombre':name,'lat':lat,'lon':lon,
            'altitud_m':int(elevation.group(1)) if elevation else None,
            'wigos':wigos.group(1) if wigos else None,
            'periodo':years.group(1) if years else None,
            'temp_media_mensual_c':vals[:12],'temp_media_anual_c':vals[12],
            'pagina_pdf':pdf_page+1,'pagina_smn':pdf_page-4})
    if len(stations)!=105 or len({s["nombre"] for s in stations})!=105:
        raise ValueError("Faltan estaciones SMN o hay estaciones repetidas")
    if sum(-55<=s['lat']<=-20 and -85<=s['lon']<=-45 for s in stations)!=99:
        raise ValueError("La cobertura de 99 estaciones continentales cambió")
    if sum(any(v is None for v in s['temp_media_mensual_c']) for s in stations)!=3:
        raise ValueError("Los valores faltantes S/D se extrajeron incorrectamente")
    for name,october in [('LA PLATA AERO',15.9),('CÓRDOBA AERO',18.3)]:
        station=next(s for s in stations if s['nombre']==name)
        if station['temp_media_mensual_c'][9]!=october:
            raise ValueError(f'Control de octubre SMN distinto: {name}')
    return {
        'fuente':'Servicio Meteorológico Nacional (2023), Estadísticas Climatológicas Normales República Argentina 1991-2020',
        'publicacion':'https://repositorio.smn.gob.ar/handle/20.500.12160/2506',
        'sha256_pdf':hashlib.sha256(path.read_bytes()).hexdigest(),
        'metodologia':'temperatura media mensual observada por estación; S/D conservado como null; NO es grilla continua',
        'meses':['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'],
        'total_estaciones':105,'estaciones':stations}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('pdf',nargs='?',help='Archivo PDF oficial SMN (si se omite: descargar repositorio SMN)')
    p.add_argument('--salida',default='web/monitoreo-extremo/normales_temperatura_smn_1991_2020.json')
    args=p.parse_args()
    filename=args.pdf
    if not filename:
        import requests,tempfile
        r=requests.get(PDF_URL,timeout=180);r.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix='.pdf') as tmp:
            tmp.write(r.content);tmp.flush()
            data=parse(tmp.name)
    else:data=parse(filename)
    dst=Path(args.salida);dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print(f"SMN validado: {data['total_estaciones']} estaciones; SHA256={data['sha256_pdf']}; {dst.stat().st_size} bytes")

if __name__=='__main__':main()
