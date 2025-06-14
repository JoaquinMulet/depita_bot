-- =============================================================================
--  SCRIPT DE REINICIO DE ESQUEMA PARA SISTEMA DE MONITOREO DE PROPIEDADES
--  Versión: Llave Compuesta (título, precio_uf)
-- =============================================================================

-- Parte 1: Eliminación de Tablas Existentes
-- Usamos DROP ... CASCADE para eliminar las tablas y todas sus dependencias (como F-keys).
DROP TABLE IF EXISTS log_ejecucion CASCADE;
DROP TABLE IF EXISTS metricas_historicas CASCADE;
DROP TABLE IF EXISTS observaciones_venta CASCADE;
DROP TABLE IF EXISTS propiedades CASCADE;

-- *** Tablas anteriores eliminadas exitosamente. ***

-- =============================================================================
--  Parte 2: Creación de la Nueva Estructura de Tablas
-- =============================================================================

-- Tabla 1: propiedades
-- Almacena las combinaciones únicas de (título, precio) que hemos encontrado.
-- Un ID serial simple actúa como Primary Key para joins eficientes, mientras que
-- una restricción UNIQUE en (titulo, precio_uf) impone la regla de negocio.
--
CREATE TABLE propiedades (
    id SERIAL PRIMARY KEY,
    titulo TEXT NOT NULL,
    precio_uf NUMERIC(10, 2) NOT NULL,
    ubicacion TEXT,
    fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    
    -- Esta es la nueva "llave de negocio" compuesta.
    CONSTRAINT propiedades_titulo_precio_key UNIQUE (titulo, precio_uf)
);

COMMENT ON TABLE propiedades IS 'Tabla de entidades para propiedades únicas, identificadas por la combinación de su título y precio en UF.';
COMMENT ON COLUMN propiedades.id IS 'Llave primaria para joins eficientes.';
COMMENT ON COLUMN propiedades.titulo IS 'El título de la publicación. Parte de la llave de negocio.';
COMMENT ON COLUMN propiedades.precio_uf IS 'El precio en UF de la publicación. Parte de la llave de negocio.';
COMMENT ON CONSTRAINT propiedades_titulo_precio_key ON propiedades IS 'Garantiza que cada combinación de título y precio sea única.';

---
-- Tabla 2: observaciones_venta
-- Log de Eventos Inmutable. Cada fila es un "avistamiento" de una propiedad en
-- un momento dado, con todos sus detalles (incluyendo el link volátil).
--
CREATE TABLE observaciones_venta (
    id SERIAL PRIMARY KEY,
    propiedad_id INTEGER NOT NULL REFERENCES propiedades(id) ON DELETE CASCADE,
    fecha_observacion TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    
    -- Almacenamos ambos valores para flexibilidad
    precio_clp BIGINT,
    precio_uf NUMERIC(10, 2), -- Este precio debe coincidir con el de la tabla 'propiedades' a la que se enlaza.
    
    superficie_util_m2 NUMERIC(10, 2),
    dormitorios INTEGER,
    
    -- Datos adicionales para contexto que pueden cambiar entre observaciones
    link TEXT, -- El link volátil ahora vive aquí, como un atributo de la observación.
    atributos_raw TEXT,
    imagen_url TEXT,
    
    -- Flag para que el analizador sepa qué procesar
    es_nueva BOOLEAN DEFAULT TRUE
);

COMMENT ON TABLE observaciones_venta IS 'Log inmutable de todos los avistamientos de propiedades. La fuente de la verdad.';
COMMENT ON COLUMN observaciones_venta.propiedad_id IS 'FK a la combinación (título, precio) a la que pertenece esta observación.';
COMMENT ON COLUMN observaciones_venta.link IS 'URL de la publicación en el momento de la observación.';

---
-- Tabla 3: metricas_historicas
-- Almacena datos derivados y calculados por el script analizador.
-- Puede ser reconstruida a partir de 'observaciones_venta'.
--
CREATE TABLE metricas_historicas (
    id SERIAL PRIMARY KEY,
    observacion_id INTEGER NOT NULL REFERENCES observaciones_venta(id) ON DELETE CASCADE,
    fecha_calculo TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    uf_por_m2 NUMERIC(10, 2)
);

COMMENT ON TABLE metricas_historicas IS 'Datos derivados. Almacena métricas calculadas como UF/m2.';

---
-- Tabla 4: log_ejecucion
-- Tabla de operabilidad para monitorear la salud de los scripts.
--
CREATE TABLE log_ejecucion (
    id SERIAL PRIMARY KEY,
    script_name TEXT NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    status TEXT NOT NULL, -- Ej: 'STARTED', 'SUCCESS', 'FAILURE'
    error_message TEXT
);

COMMENT ON TABLE log_ejecucion IS 'Registro de auditoría y monitoreo para las ejecuciones de los scripts.';

-- *** Nuevas tablas creadas exitosamente. ***

-- =============================================================================
--  Parte 3: Creación de Índices para Rendimiento
-- =============================================================================

-- PostgreSQL crea automáticamente un índice para la restricción UNIQUE en (titulo, precio_uf).

-- Índice para buscar rápidamente todas las observaciones de una propiedad específica.
CREATE INDEX idx_observaciones_propiedad_id ON observaciones_venta(propiedad_id);

-- Índice parcial para que el analizador encuentre rápidamente las filas nuevas.
CREATE INDEX idx_observaciones_nuevas ON observaciones_venta(id) WHERE es_nueva = TRUE;

-- Índice para buscar la última ejecución de un script específico.
CREATE INDEX idx_log_script_tiempo ON log_ejecucion(script_name, start_time DESC);

-- *** Índices creados exitosamente. ***
-- *** ¡Esquema de base de datos reiniciado y listo para usar! ***
-- =============================================================================
--  Fin del Script
-- =============================================================================