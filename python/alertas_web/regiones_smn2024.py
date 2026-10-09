"""Digitalización geográfica PRELIMINAR de las regiones de umbrales del SMN.
Fuente: "Umbrales para los alertas", 2a edición, julio 2024, pp. 4 y 6.
No es un producto oficial GIS; los bordes requieren validación operacional.
"""
import base64
import zlib
import numpy as np
from scipy.ndimage import minimum_filter, maximum_filter
LLUVIA_B64 = "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"
VIENTO_B64 = "eNrt3etS4zoQhdGW2u//zOcww4BDbk6w1K3e3/5FUSmHhe7tGMwIIYQQQgghhJCQtCYHFiO3dpvcv1MRvMs1uBS53cgNcS8N/kvuvSa53SX3ouS74t6Lkm+D++0gri/udYdxL0t+FVxT3B+moLj3yuTW3iD3esO4Mrm9Se7FwIUnsCZH/o2464lXNLdfipdDtxPEK7FbO03ca3hfEec3t3a2uMuBc5NHeFObR4HTkseBs5pHgnOaB4sTooeD05lniJOhD4oL9e1D4lKjuR2OHrlDPlU883cyR/yMO7MbxINtbs/PMIozivvoQTxPnKmJ55CTzNPpxGOX4rmrdvg8PVvccokNcc1e3ROKJ83UVcQvgNOIp4EVxD2lePgpMd3qJAce1sY1wXcsH98pDf7piar8taninS03eIA4qrLb0ohLlTBTle4Bx4gDbr1soeJ5YP8mbVucOObu2vaYXBL8bd6u+UXBn+oL/XDxdPAf2nYjk8TTb5Fv9zNFbJnE2wSx5RW3AuDn4uHkdODh/TqheG+uAX4u3saJLbu4lQAfEG+IFwWHi80s6zj+Iq8OjhWbmtiSi7ezxRYo3o6LP75YGmzHwbuagYz4KyuD/xRuI8Sh4AixRfbpN8Tb4mDE48W2nnhbW7xtMo0c1cTRYqEm1hO7mtgb4uqLUwubqhEjRpxAvMntqlcVW4w4EPxmyWd58fQ614ririZetsj1dkkA8ULgN5dkxIgXEDeZies9cu9ijdzXFrcAsVwTBw/jl0vWq4P/J7tWE3+StcQ2t41zgAXFTUrsiOvP1YjLi+X2XK8uT7Qx4nLg9cVNTaxXEAgo6/W1RvHiz4T8q/lMF6/1WMjaj7O98zkQnSf4zhb3RWbqE8V9icX4VHFfo4nXFluwuCMuLzbEiFmPEU8Rrz1V3/l8QJ+VkFvlUmL3O+RelOz+RQ4T9/lg91jxRLPvxFukuE8Xe9skxL5LsLgjHi92PbGrjWNFsQusx/6ILCG+UNfect0yl9xXuz8wS4k/0F7y6OQPU/msGGvOJPZq4BRiQ1x9IBvi6t3a0om9lveIeKDaQhJHNsssfsV87LUWFz/RfPS1Fho/j3zwtbYK+Cn5yGttIe5T99OXWXz89zkothzxc3It/rh4Ou2J4n/mS3HK+LnkBcQnkv1yHCuI/XLiEgD/COLyYMT1wYjp1IhZm2hixHRqxIjZfyAuSXbE9OpjLCnxg+tYafHVleoWbm9fLG9t3nwE2UxGvEIQI65HRky3Rox4PTBiOvWLpycB7s68QoufW9/RErstMqpl7rwgPrGcqSHeX0uniWXFMhPX59U09piL7a4dssAJSowrWdqjeksNhDrX+mCTA/+WbLQxYno1jczqhJhOjRjxcLXJkU2NrAY2wNVnavbUHJxKoW2JzzKdSLbFo+Z9lWxiYDMxMWDAgBEjzi02UyPLiWlixExctDFixJARM1tT8xkC1itjViBTnIdcEM2dRT4jwA1zPoSKGHEpMU1cHowYMWKmaraYnJs4G8eKAQOuJTbAxcVmYmRTEwOmSwMGvNbCJAfW22shZj9NEyNGjBgxYhYnxGyqdc9N1PP4dHHBxwTkHovQ+/Mu/N0AnujSfjSzlPgQvZLYxMRHuzdixPXmbMSIC+5EECP+9R5o9u81QOy7t734AbKcKOa9ZVmxXVw7IXngexriouR7fXrehB0ljmngycenH//ePWynM7mRr5fiymdkvzVpJdx+Dmjf3dd5tu4jyPurJT2pDPyx0h7NBpIzHymNEEIIIazH87ddiBEzjglJ360FVyfXEzvi+mJHXF/semLXE7ue2BHXF7ue2PXErieWMLscWeKBkSdiR1xf7Hri2mahB96eiOuaeWDmvthV/sno/lU64pLd+3GnrrxcuWuemI0QQgghhBBSLP8B4bRIVg=="
# Coordenadas: pixel_x=ax*lon+bx, pixel_y=ay*lat+by (registro afín aproximado).
ESPEC = {
 "LLUVIA":(425,265,8.75620521,710.61848224,-11.0283477,-230.25304717,LLUVIA_B64),
 "VIENTO":(451,242,9.48203555,727.82047114,-12.0020818,-251.98664181,VIENTO_B64)
}
IDS={"LLUVIA":{i:f"PP_R{i}" for i in range(1,9)},
     "VIENTO":{1:"WIND_R1",2:"WIND_R2",3:"WIND_R3",4:"ZONDA_SIN_UMBRAL_DE_VIENTO"}}
def mascara(tipo):
 h,w,ax,bx,ay,by,raw=ESPEC[tipo]
 a=np.frombuffer(zlib.decompress(base64.b64decode(raw)),dtype=np.uint8)
 if a.size!=h*w:raise ValueError("Máscara de regiones corrupta")
 return a.reshape(h,w)

def asignar_nombres(tipo,latitudes,longitudes,margen=2):
 """Devuelve una matriz de IDs, vacíos si no se conoce región/posición segura.
 Un margen de 2 píxeles evita atribuir umbrales en bordes de imagen raster.
 """
 h,w,ax,bx,ay,by,_=ESPEC[tipo]
 m=mascara(tipo)
 if margen not in (0,1,2,3,4):raise ValueError("Margen no admitido")
 if margen:
  k=2*margen+1
  estable=(minimum_filter(m,size=k,mode="constant",cval=0)==
          maximum_filter(m,size=k,mode="constant",cval=255))&(m>0)
 else:estable=m>0
 X,Y=np.meshgrid(np.asarray(longitudes,dtype=float),np.asarray(latitudes,dtype=float))
 x=np.rint(X*ax+bx).astype("int32")
 y=np.rint(Y*ay+by).astype("int32")
 ok=(x>=0)&(x<w)&(y>=0)&(y<h)
 ids=np.zeros(X.shape,dtype=np.uint8)
 ids[ok]=m[y[ok],x[ok]]
 ok[ok] &= estable[y[ok],x[ok]]
 ids[~ok]=0
 if tipo=="VIENTO":ids[ids==4]=0 # Zonda requiere su propio diagnóstico.
 out=np.full(ids.shape,"",dtype="<U16")
 for i,name in IDS[tipo].items():
  if tipo=="VIENTO" and i==4:continue
  out[ids==i]=name
 return out

def exportar_geojson(tipo,geom_pais,margen=2):
 """Capa cartográfica para auditoría; se recorta a provincias argentinas."""
 from affine import Affine
 from rasterio.features import shapes
 from shapely.geometry import shape,mapping
 from shapely.ops import unary_union
 h,w,ax,bx,ay,by,_=ESPEC[tipo]
 m=mascara(tipo).copy()
 if margen:
  k=2*margen+1
  seguro=(minimum_filter(m,size=k,mode="constant",cval=0)==
          maximum_filter(m,size=k,mode="constant",cval=255))
  m[~seguro]=0
 if tipo=="VIENTO":m[m==4]=0
 trans=Affine(1/ax,0,(-bx-.5)/ax,0,1/ay,(-by-.5)/ay)
 grupos={}
 for geo,v in shapes(m,mask=m>0,connectivity=8,transform=trans):
  n=int(v)
  s=shape(geo)
  if s.area>.004:grupos.setdefault(n,[]).append(s)
 feats=[]
 for n,polys in grupos.items():
  g=unary_union(polys).buffer(.03).buffer(-.03).intersection(geom_pais)
  if g.is_empty:continue
  g=g.simplify(.02,preserve_topology=True)
  feats.append({"type":"Feature","properties":{
    "region":IDS[tipo][n],"fenomeno":tipo,
    "fuente":"SMN, Umbrales para los alertas, 2a edición 2024",
    "estado":"PRELIMINAR_SIN_VALIDACION_GIS",
    "pagina":4 if tipo=="LLUVIA" else 6,
    "margen_pixeles":margen},
    "geometry":mapping(g)})
 return {"type":"FeatureCollection",
         "metadata":{"uso_operativo_autorizado":False,
                     "fuente":"PDF SMN julio 2024, georreferenciado aproximado",
                     "borde_no_asegurado":True},
         "features":feats}
