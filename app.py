import pandas as pd
import numpy as np
import dash
from dash import dcc, html
import plotly.express as px
import plotly.graph_objects as go
from dash.dependencies import Input, Output
from dash.exceptions import PreventUpdate
import json
import os
import geopandas as gpd 


#Función para procesar los datos geográficos
def procesar_datos_geograficos():
    # Rutas de entrada
    # Cambiar la línea de definición de ruta
    shapefile_path = os.path.join(os.path.dirname(__file__), 'COLOMBIA.shp')
    csv_path = "educacion_superior.csv"
    output_geojson_path = "colombia_educacion.geojson"
    output_puntos_path = "colombia_educacion_puntos.geojson"
    
    # Comprobar si los GeoJSON ya existen para no volver a procesarlos
    if os.path.exists(output_geojson_path) and os.path.exists(output_puntos_path):
        print("Archivos GeoJSON encontrados. Cargando directamente...")
        with open(output_geojson_path, 'r') as f:
            geojson_data = json.load(f)
        with open(output_puntos_path, 'r') as f:
            geojson_puntos = json.load(f)
            
        # Intentar identificar la columna de departamentos
        dept_cols = ['DEPARTAMEN', 'NOMBRE_DEP', 'DPTO', 'NAME_1', 'DEPARTAMENTO', 'NOM_DEPART']
        dept_col = None
        
        for col in dept_cols:
            if geojson_data['features'] and col in geojson_data['features'][0]['properties']:
                dept_col = col
                break
        
        return {
            'poligonos': geojson_data,
            'puntos': geojson_puntos,
            'dept_col': dept_col
        }
    
    # Si no existen, importamos geopandas y procesamos los archivos
    try:
        # Cargar el shapefile
        gdf_colombia = gpd.read_file(shapefile_path)
        
        # Cargar el CSV
        df_educacion = pd.read_csv(csv_path)
        
        # Crear GeoDataFrame de puntos
        gdf_puntos = gpd.GeoDataFrame(
            df_educacion, 
            geometry=gpd.points_from_xy(df_educacion.Longitud, df_educacion.Latitud),
            crs="EPSG:4326"
        )
        
        # Identificar columna de departamentos
        dept_col = None
        posibles_cols = ['DEPARTAMEN', 'NOMBRE_DEP', 'DPTO', 'NAME_1', 'DEPARTAMENTO', 'NOM_DEPART']
        for col in posibles_cols:
            if col in gdf_colombia.columns:
                dept_col = col
                break
        
        if dept_col is None:
            # Usar la primera columna que parezca contener nombres
            for col in gdf_colombia.columns:
                if gdf_colombia[col].dtype == 'object' and gdf_colombia[col].nunique() > 20:
                    dept_col = col
                    break
        
        # Convertir a GeoJSON
        gdf_colombia['id'] = gdf_colombia.index
        geojson_data = json.loads(gdf_colombia.to_json())
        geojson_puntos = json.loads(gdf_puntos.to_json())
        
        # Agregar datos por departamento
        if 'Departamento' in df_educacion.columns:
            # Agregar datos de estudiantes por departamento
            estudiantes_por_depto = df_educacion.groupby('Departamento')['Estudiantes'].sum().reset_index()
            instituciones_por_depto = df_educacion.groupby('Departamento')['ID'].count().reset_index()
            instituciones_por_depto.rename(columns={'ID': 'NumInstituciones'}, inplace=True)
            
            # Unir los datos
            datos_por_depto = pd.merge(estudiantes_por_depto, instituciones_por_depto, on='Departamento')
            
            # Unir datos a las geometrías
            for feature in geojson_data['features']:
                dept_name = feature['properties'][dept_col]
                # Buscar el departamento en los datos agregados
                match = datos_por_depto[datos_por_depto['Departamento'].str.upper() == dept_name.upper()]
                if not match.empty:
                    feature['properties']['Estudiantes'] = int(match['Estudiantes'].values[0])
                    feature['properties']['NumInstituciones'] = int(match['NumInstituciones'].values[0])
                else:
                    feature['properties']['Estudiantes'] = 0
                    feature['properties']['NumInstituciones'] = 0
        
        # Guardar GeoJSON
        with open(output_geojson_path, 'w') as f:
            json.dump(geojson_data, f)
        
        with open(output_puntos_path, 'w') as f:
            json.dump(geojson_puntos, f)
        
        return {
            'poligonos': geojson_data,
            'puntos': geojson_puntos,
            'dept_col': dept_col
        }
    
    except Exception as e:
        print(f"Error al procesar datos geográficos: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

# Procesar datos geográficos
try:
    geo_data = procesar_datos_geograficos()
    dept_col = geo_data['dept_col'] if geo_data else None
except Exception as e:
    print(f"Error al inicializar datos geográficos: {str(e)}")
    geo_data = None
    dept_col = None

# Carga de datos
df = pd.read_csv('educacion_superior.csv')

# Preparar datos para las gráficas
estudiantes_por_nivel = df.groupby('Nivel')['Estudiantes'].sum().reset_index()
estudiantes_por_departamento = df.groupby('Departamento')['Estudiantes'].sum().sort_values(ascending=False).head(10).reset_index()
estudiantes_por_institucion = df.groupby('Institución')['Estudiantes'].sum().sort_values(ascending=False).head(10).reset_index()

# Calcular estadísticas básicas
total_estudiantes = df['Estudiantes'].sum()
total_instituciones = df['Institución'].nunique()
total_departamentos = df['Departamento'].nunique()
promedio_estudiantes = df['Estudiantes'].mean()

# Inicializar la aplicación Dash
app = dash.Dash(__name__, title='Análisis de Educación Superior')

# Diseño de la aplicación
app.layout = html.Div([
    # Título principal
    html.Div([
        html.H1('Análisis de Educación Superior en Colombia'),
        html.P('Exploración de datos sobre instituciones educativas de nivel superior. Eliana Fuentes')
    ], style={'textAlign': 'center', 'padding': '20px', 'backgroundColor': '#f2f2f2'}),
    
    # Tabs para navegar entre contexto, visualizaciones, georreferenciación y conclusiones
    dcc.Tabs([
        # Tab de Contextualización
        dcc.Tab(label='Contextualización', children=[
            html.Div([
                html.H2('Contextualización: Análisis de la Educación Superior en Colombia', 
                       style={'textAlign': 'center', 'marginTop': '20px', 'color': '#2c3e50'}),
                
                html.H3('Introducción', style={'color': '#3498db', 'marginTop': '30px'}),
                html.P('El presente análisis se enfoca en explorar la distribución y características de las instituciones '
                       'de educación superior en Colombia. Utilizando datos del Ministerio de Educación Nacional, este '
                       'estudio ofrece una visión integral del panorama educativo a nivel terciario en el país, considerando '
                       'variables como la distribución geográfica, niveles educativos y población estudiantil.'),
                
                html.H3('Estructura de los Datos', style={'color': '#3498db', 'marginTop': '30px'}),
                html.P('La base de datos analizada contiene información sobre instituciones de educación superior en Colombia '
                       'con los siguientes campos:'),
                html.Ul([
                    html.Li('ID: Identificador único de cada institución'),
                    html.Li('Departamento: División administrativa territorial donde se ubica la institución'),
                    html.Li('Latitud/Longitud: Coordenadas geográficas para ubicación espacial'),
                    html.Li('Nivel: Categoría educativa (Pregrado, Posgrado)'),
                    html.Li('Estudiantes: Cantidad de alumnos matriculados'),
                    html.Li('Institución: Nombre oficial de la entidad educativa')
                ]),
        
        # Tab de Conclusiones (NUEVO)
        dcc.Tab(label='Conclusiones', children=[
            html.Div([
                html.H2('Análisis y Conclusiones del Estudio', 
                       style={'textAlign': 'center', 'marginTop': '20px', 'color': '#2c3e50'}),
                
                html.Div([
                    html.H3('Distribución por Nivel Educativo', style={'color': '#3498db', 'marginTop': '30px'}),
                    html.P('El análisis de la distribución de estudiantes por nivel educativo revela un balance relativamente equilibrado '
                           'entre los cuatro niveles principales de formación en Colombia. Con un 26.8% de estudiantes en programas '
                           'Tecnológicos, 25.9% en Profesionales, 24.4% en Técnicos y 22.9% en Posgrado, se evidencia una distribución '
                           'bastante homogénea que sugiere una diversificación en la oferta educativa superior.'),
                    html.P('La similitud en los porcentajes indica que no hay una concentración desproporcionada en ningún nivel específico, '
                           'lo que refleja un sistema educativo que atiende diferentes necesidades formativas y perfiles de estudiantes. '
                           'Este equilibrio podría interpretarse como una respuesta adecuada a las demandas del mercado laboral colombiano, '
                           'que requiere profesionales con diversos niveles de cualificación.')
                ], style={'backgroundColor': 'white', 'padding': '20px', 'borderRadius': '10px', 'boxShadow': '0px 0px 10px #ddd', 'marginBottom': '20px'}),
                
                html.Div([
                    html.H3('Concentración Geográfica', style={'color': '#3498db', 'marginTop': '10px'}),
                    html.P('La gráfica de los 10 departamentos con mayor número de estudiantes muestra una marcada concentración en '
                           'Cundinamarca (que incluye Bogotá D.C.), seguido por Atlántico, Magdalena, Antioquia y Nariño. Esta distribución '
                           'refleja la centralización histórica de la educación superior en Colombia, principalmente en las grandes '
                           'áreas metropolitanas y capitales departamentales.'),
                    html.P('Es notable que los cinco primeros departamentos concentran una proporción significativa del total de estudiantes, '
                           'evidenciando desigualdades territoriales en el acceso a la educación superior. Esta centralización plantea '
                           'desafíos importantes para las políticas de descentralización educativa y el acceso equitativo a formación '
                           'de calidad en regiones menos pobladas o más alejadas de los principales centros urbanos.')
                ], style={'backgroundColor': 'white', 'padding': '20px', 'borderRadius': '10px', 'boxShadow': '0px 0px 10px #ddd', 'marginBottom': '20px'}),
                
                html.Div([
                    html.H3('Concentración Institucional', style={'color': '#3498db', 'marginTop': '10px'}),
                    html.P('El análisis de las 10 instituciones con mayor número de estudiantes revela que existe una alta concentración '
                           'en pocas universidades. La Universidad B destaca significativamente con aproximadamente 180,000 estudiantes, '
                           'seguida por las Universidades C y A con números considerablemente menores.'),
                    html.P('Esta concentración institucional puede representar tanto ventajas como desventajas para el sistema educativo. '
                           'Por un lado, permite economías de escala y posiblemente mayor calidad debido a la concentración de recursos; '
                           'por otro, plantea interrogantes sobre la diversidad de enfoques educativos y la competencia en el sector.')
                ], style={'backgroundColor': 'white', 'padding': '20px', 'borderRadius': '10px', 'boxShadow': '0px 0px 10px #ddd', 'marginBottom': '20px'}),
                
                html.Div([
                    html.H3('Distribución del Tamaño de las Instituciones', style={'color': '#3498db', 'marginTop': '10px'}),
                    html.P('El histograma de la distribución del número de estudiantes por institución muestra un patrón interesante: '
                           'existe un pico notable alrededor de los 2,500 estudiantes, indicando que muchas instituciones tienen un '
                           'tamaño similar en esta categoría.'),
                    html.P('La distribución presenta una forma relativamente normal con cierta asimetría, lo que sugiere un ecosistema '
                           'educativo con predominio de instituciones de tamaño mediano, complementadas por algunas muy grandes y varias '
                           'pequeñas. Esta diversidad de tamaños puede ser positiva para el sistema, ofreciendo distintos entornos de '
                           'aprendizaje adaptados a diferentes necesidades y contextos.')
                ], style={'backgroundColor': 'white', 'padding': '20px', 'borderRadius': '10px', 'boxShadow': '0px 0px 10px #ddd', 'marginBottom': '20px'}),
                
                html.Div([
                    html.H3('Distribución por Nivel (Box Plot)', style={'color': '#3498db', 'marginTop': '10px'}),
                    html.P('El box plot que compara la distribución del número de estudiantes por nivel educativo revela que todos los '
                           'niveles tienen rangos similares, con medianas cercanas a los 2,000-2,500 estudiantes por institución.'),
                    html.P('No se observan diferencias drásticas entre los niveles en términos de dispersión o valores atípicos, lo que '
                           'sugiere que la capacidad institucional es relativamente consistente a través de los diferentes tipos de '
                           'formación. Esto podría indicar que las instituciones que ofrecen diversos niveles educativos mantienen '
                           'proporciones similares de estudiantes en cada nivel, sin una especialización extrema en un nivel particular.')
                ], style={'backgroundColor': 'white', 'padding': '20px', 'borderRadius': '10px', 'boxShadow': '0px 0px 10px #ddd', 'marginBottom': '20px'}),
                
                html.Div([
                    html.H3('Conclusiones Generales', style={'color': '#3498db', 'marginTop': '10px'}),
                    html.P('El análisis integral de los datos sobre educación superior en Colombia revela un sistema relativamente '
                           'balanceado en términos de niveles educativos, pero con marcadas disparidades geográficas e institucionales. '
                           'Estos hallazgos plantean importantes consideraciones para la formulación de políticas educativas:'),
                    html.Ul([
                        html.Li('Necesidad de fortalecer la descentralización educativa para equilibrar la oferta entre departamentos'),
                        html.Li('Importancia de supervisar la concentración institucional para garantizar calidad y accesibilidad'),
                        html.Li('Oportunidad para desarrollar políticas que mantengan el balance entre niveles educativos, adaptándolos '
                                'a las necesidades cambiantes del mercado laboral y la sociedad'),
                        html.Li('Potencial para implementar estrategias de integración entre diferentes niveles formativos, aprovechando '
                                'la similitud en sus distribuciones')
                    ]),
                    html.P('En síntesis, Colombia muestra un sistema de educación superior diversificado y con potencial de desarrollo, '
                           'aunque con desafíos importantes en términos de equidad territorial e institucional que requerirán atención '
                           'prioritaria en las próximas décadas.')
                ], style={'backgroundColor': 'white', 'padding': '20px', 'borderRadius': '10px', 'boxShadow': '0px 0px 10px #ddd', 'marginBottom': '20px'})
            ], style={'padding': '20px'})
        ]),
                           
                
            ], style={'padding': '20px', 'backgroundColor': 'white', 'boxShadow': '0px 0px 10px #ddd', 'margin': '20px', 'borderRadius': '5px'})
        ]),
        
        # Tab de Visualizaciones
        dcc.Tab(label='Visualizaciones', children=[
    
            # Tarjetas de estadísticas
            html.Div([
                html.Div([
                    html.H4('Total Estudiantes'),
                    html.H2(f"{total_estudiantes:,}"),
                ], className='stat-card'),
                html.Div([
                    html.H4('Instituciones'),
                    html.H2(f"{total_instituciones}"),
                ], className='stat-card'),
                html.Div([
                    html.H4('Departamentos'),
                    html.H2(f"{total_departamentos}"),
                ], className='stat-card'),
                html.Div([
                    html.H4('Promedio Estudiantes'),
                    html.H2(f"{promedio_estudiantes:.0f}"),
                ], className='stat-card'),
            ], style={'display': 'flex', 'justifyContent': 'space-around', 'margin': '20px 0'}),
            
            # Gráfica 1: Distribución de estudiantes por nivel
            html.Div([
                html.H3('Distribución de Estudiantes por Nivel Educativo'),
                dcc.Graph(
                    id='grafica-nivel',
                    figure=px.pie(
                        estudiantes_por_nivel, 
                        values='Estudiantes', 
                        names='Nivel',
                        title='Distribución de Estudiantes por Nivel Educativo',
                        color_discrete_sequence=px.colors.qualitative.Pastel,
                        hole=0.3
                    )
                )
            ], style={'width': '48%', 'display': 'inline-block', 'padding': '10px', 'boxShadow': '0px 0px 10px #ccc', 'margin': '10px'}),
            
            # Gráfica 2: Top 10 departamentos por número de estudiantes
            html.Div([
                html.H3('Top 10 Departamentos por Número de Estudiantes'),
                dcc.Graph(
                    id='grafica-departamentos',
                    figure=px.bar(
                        estudiantes_por_departamento, 
                        x='Departamento', 
                        y='Estudiantes',
                        title='Top 10 Departamentos por Número de Estudiantes',
                        color='Estudiantes',
                        color_continuous_scale=px.colors.sequential.Blues
                    )
                )
            ], style={'width': '48%', 'display': 'inline-block', 'padding': '10px', 'boxShadow': '0px 0px 10px #ccc', 'margin': '10px'}),
            
            # Gráfica 3: Top 10 instituciones por número de estudiantes
            html.Div([
                html.H3('Top 10 Instituciones por Número de Estudiantes'),
                dcc.Graph(
                    id='grafica-instituciones',
                    figure=px.bar(
                        estudiantes_por_institucion, 
                        x='Estudiantes', 
                        y='Institución',
                        title='Top 10 Instituciones por Número de Estudiantes',
                        orientation='h',
                        color='Estudiantes',
                        color_continuous_scale=px.colors.sequential.Greens
                    ).update_layout(yaxis={'categoryorder':'total ascending'})
                )
            ], style={'width': '48%', 'display': 'inline-block', 'padding': '10px', 'boxShadow': '0px 0px 10px #ccc', 'margin': '10px'}),
            
            # Gráfica 4: Distribución de estudiantes (histograma)
            html.Div([
                html.H3('Distribución del Número de Estudiantes por Institución'),
                dcc.Graph(
                    id='grafica-distribucion',
                    figure=px.histogram(
                        df, 
                        x='Estudiantes',
                        nbins=30,
                        title='Distribución del Número de Estudiantes por Institución',
                        color_discrete_sequence=['#636EFA']
                    ).update_layout(bargap=0.1)
                )
            ], style={'width': '48%', 'display': 'inline-block', 'padding': '10px', 'boxShadow': '0px 0px 10px #ccc', 'margin': '10px'}),
            
            # Gráfica 5: Box plot de estudiantes por nivel
            html.Div([
                html.H3('Distribución de Estudiantes por Nivel (Box Plot)'),
                dcc.Graph(
                    id='grafica-boxplot',
                    figure=px.box(
                        df, 
                        x='Nivel', 
                        y='Estudiantes',
                        title='Distribución de Estudiantes por Nivel (Box Plot)',
                        color='Nivel'
                    )
                )
            ], style={'width': '100%', 'padding': '10px', 'boxShadow': '0px 0px 10px #ccc', 'margin': '10px'}),
            
            # Selector para filtrar por Departamento
            html.Div([
                html.H3('Análisis por Departamento'),
                dcc.Dropdown(
                    id='dropdown-departamento',
                    options=[{'label': dep, 'value': dep} for dep in sorted(df['Departamento'].unique())],
                    value=df['Departamento'].iloc[0],
                    clearable=False
                ),
                dcc.Graph(id='grafica-filtrada')
            ], style={'width': '100%', 'padding': '10px', 'boxShadow': '0px 0px 10px #ccc', 'margin': '10px'}),
            
            # Pie de página interno tab visualizaciones
            html.Div([
                html.P('Análisis de datos de Educación Superior - Desarrollado con Dash y Plotly')
            ], style={'textAlign': 'center', 'padding': '20px', 'backgroundColor': '#f2f2f2', 'marginTop': '20px'})
        ]),
        
        # Tab de Georreferenciación (NUEVO)
        dcc.Tab(label='Georreferenciación', children=[
            html.Div([
                html.H2('Georreferenciación: Distribución Espacial de Instituciones de Educación Superior', 
                       style={'textAlign': 'center', 'marginTop': '20px', 'color': '#2c3e50'}),
                
                # Estado del procesamiento geográfico
                html.Div(id='estado-geoprocesamiento', style={'textAlign': 'center', 'marginTop': '10px', 'color': '#e74c3c'}),
                
                # Selector para variable a visualizar en el mapa
                html.Div([
                    html.Label('Seleccione variable a visualizar:'),
                    dcc.RadioItems(
                        id='variable-mapa',
                        options=[
                            {'label': 'Estudiantes por Departamento', 'value': 'Estudiantes'},
                            {'label': 'Número de Instituciones', 'value': 'NumInstituciones'}
                        ],
                        value='Estudiantes',
                        labelStyle={'display': 'block', 'margin': '10px 0'}
                    )
                ], style={'width': '300px', 'margin': '20px auto', 'padding': '15px', 'backgroundColor': 'white', 'borderRadius': '5px', 'boxShadow': '0px 0px 5px #ddd'}),
                
                # Selector para mostrar/ocultar puntos de instituciones
                html.Div([
                    html.Label('Visualización de instituciones:'),
                    dcc.Checklist(
                        id='mostrar-instituciones',
                        options=[
                            {'label': 'Mostrar puntos de instituciones', 'value': 'mostrar'}
                        ],
                        value=['mostrar'],
                        labelStyle={'display': 'block', 'margin': '10px 0'}
                    )
                ], style={'width': '300px', 'margin': '20px auto', 'padding': '15px', 'backgroundColor': 'white', 'borderRadius': '5px', 'boxShadow': '0px 0px 5px #ddd'}),
                
                # Mapa coroplético
                html.Div([
                    dcc.Graph(id='mapa-colombia', style={'height': '700px'})
                ], style={'width': '100%', 'padding': '10px', 'boxShadow': '0px 0px 10px #ccc', 'margin': '20px 0', 'backgroundColor': 'white', 'borderRadius': '5px'}),
                
                # Información adicional sobre la georreferenciación
                html.Div([
                    html.H3('Análisis Geoespacial', style={'color': '#3498db', 'marginTop': '20px'}),
                    html.P('La visualización geoespacial permite identificar patrones de distribución territorial de las instituciones '
                           'educativas y detectar disparidades regionales en la oferta educativa de nivel superior. Este análisis '
                           'revela áreas con alta concentración de instituciones (principalmente en centros urbanos) y regiones con '
                           'baja cobertura que podrían requerir intervenciones específicas.'),
                    html.P('La georreferenciación de instituciones educativas facilita:'),
                    html.Ul([
                        html.Li('Identificación de áreas de oportunidad para nuevas instituciones o programas'),
                        html.Li('Análisis de la equidad territorial en el acceso a educación superior'),
                        html.Li('Evaluación de la distancia entre instituciones y centros poblados'),
                        html.Li('Planificación de políticas educativas con enfoque regional')
                    ]),
                    html.P('Los datos visualizados en este mapa han sido integrados a partir del archivo shapefile de Colombia '
                           'ubicado en /Users/elianafuentes/Documents/Docker/COLOMBIA/COLOMBIA.shp y la base de datos de educación superior.')
                ], style={'padding': '20px', 'backgroundColor': 'white', 'boxShadow': '0px 0px 10px #ddd', 'margin': '20px', 'borderRadius': '5px'})
            ], style={'padding': '20px'})
        ])
    ], style={'marginBottom': '20px'}),
    
    # Pie de página general
    html.Div([
        html.P('© 2025 Análisis de Educación Superior en Colombia')
    ], style={'textAlign': 'center', 'padding': '20px', 'backgroundColor': '#f2f2f2', 'marginTop': '20px'})
], style={'maxWidth': '1200px', 'margin': '0 auto', 'fontFamily': 'Arial, sans-serif'})

# Callbacks
# Callback para actualizar la gráfica filtrada
@app.callback(
    Output('grafica-filtrada', 'figure'),
    [Input('dropdown-departamento', 'value')]
)
def actualizar_grafica(departamento_seleccionado):
    datos_filtrados = df[df['Departamento'] == departamento_seleccionado]
    datos_agrupados = datos_filtrados.groupby('Nivel')['Estudiantes'].sum().reset_index()
    
    fig = px.bar(
        datos_agrupados, 
        x='Nivel', 
        y='Estudiantes',
        title=f'Estudiantes por Nivel Educativo en {departamento_seleccionado}',
        color='Nivel'
    )
    
    return fig

# Callback para mostrar estado del procesamiento geográfico
@app.callback(
    Output('estado-geoprocesamiento', 'children'),
    [Input('variable-mapa', 'value')]
)
def actualizar_estado(variable):
    if geo_data is None:
        return html.Div([
            html.H4('Error al procesar datos geográficos', style={'color': '#e74c3c'}),
            html.P('No se pudo procesar el archivo shapefile. Verifique la ruta: /Users/elianafuentes/Documents/Docker/COLOMBIA/COLOMBIA.shp')
        ])
    return ''

# Callback para actualizar el mapa
@app.callback(
    Output('mapa-colombia', 'figure'),
    [Input('variable-mapa', 'value'),
     Input('mostrar-instituciones', 'value')]
)
def actualizar_mapa(variable, mostrar_instituciones):
    if geo_data is None:
        # Devolver un mapa vacío con mensaje de error
        fig = go.Figure()
        fig.add_annotation(
            text="No se pudieron cargar los datos geográficos",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20, color="#e74c3c")
        )
        fig.update_layout(
            height=500,
            title="Error al cargar datos geográficos"
        )
        return fig
    
    # Iniciar figura
    fig = go.Figure()
    
    # Añadir capa de departamentos (coroplético)
    geojson_data = geo_data['poligonos']
    
    # Determinar color y título en base a la variable seleccionada
    if variable == 'Estudiantes':
        color_scale = 'Blues'
        titulo = 'Estudiantes por Departamento'
    else:  # NumInstituciones
        color_scale = 'Greens'
        titulo = 'Número de Instituciones por Departamento'
    
    # Extraer valores de la propiedad para la escala de color
    values = []
    locations = []
    
    for feature in geojson_data['features']:
        if variable in feature['properties'] and dept_col in feature['properties']:
            values.append(feature['properties'][variable])
            locations.append(feature['properties'][dept_col])
    
    # Añadir capa coroplética
    fig.add_choroplethmapbox(
        geojson=geojson_data,
        locations=locations,
        z=values,
        featureidkey=f'properties.{dept_col}',
        colorscale=color_scale,
        marker_opacity=0.7,
        marker_line_width=0.5,
        colorbar=dict(
            title=variable,
            ticksuffix=' ',
            len=0.7
        ),
        hovertemplate='<b>%{location}</b><br>' +
                      f'{variable}: %{{z}}<extra></extra>'
    )
    
    # Añadir puntos de instituciones si se selecciona
    if 'mostrar' in mostrar_instituciones:
        # Añadir puntos de instituciones
        fig.add_scattermapbox(
            lat=df['Latitud'],
            lon=df['Longitud'],
            mode='markers',
            marker=dict(
                size=8,
                color='red',
                opacity=0.7
            ),
            text=df['Institución'],
            hoverinfo='text',
            hovertemplate='<b>%{text}</b><br>' +
                          'Estudiantes: ' + df['Estudiantes'].astype(str) + '<br>' +
                          'Nivel: ' + df['Nivel'] + '<extra></extra>'
        )
    
    # Actualizar layout
    fig.update_layout(
        mapbox_style="carto-positron",
        mapbox_zoom=5,
        mapbox_center={"lat": 4.5709, "lon": -74.2973},
        margin={"r": 0, "t": 50, "l": 0, "b": 0},
        height=700,
        title=f'Mapa de {titulo} en Colombia',
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01
        )
    )
    
    return fig

# Estilos CSS personalizados
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            .stat-card {
                padding: 15px;
                background-color: white;
                border-radius: 5px;
                box-shadow: 0px 0px 10px #ddd;
                text-align: center;
                width: 20%;
            }
            .stat-card h2 {
                margin: 5px 0;
                color: #2c3e50;
            }
            .stat-card h4 {
                margin: 5px 0;
                color: #7f8c8d;
            }
            /* Estilos para las pestañas */
            .dash-tab {
                border-radius: 5px 5px 0 0;
                padding: 12px 24px;
                font-weight: 600;
            }
            .dash-tab--selected {
                background-color: #3498db;
                color: white;
            }
            /* Estilos para la contextualización */
            ul, ol {
                margin-left: 25px;
            }
            li {
                margin-bottom: 8px;
                line-height: 1.5;
            }
            p {
                line-height: 1.6;
                margin-bottom: 15px;
                text-align: justify;
            }
            /* Animación para cargar el mapa */
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            .mapa-container {
                animation: fadeIn 1s ease-in-out;
            }
            /* Estilos para la leyenda del mapa */
            .legend-title {
                font-weight: bold;
                margin-bottom: 5px;
            }
            .legend-item {
                display: flex;
                align-items: center;
                margin-bottom: 5px;
            }
            .legend-color {
                width: 20px;
                height: 15px;
                margin-right: 8px;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''
server = app.server 


# Correr la aplicación
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8050))
    app.run_server(host='0.0.0.0', port=port, debug=True)