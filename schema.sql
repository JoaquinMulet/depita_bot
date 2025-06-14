-- =============================================================================
--  Esquema de Base de Datos para el Sistema de Monitoreo de Propiedades
-- =============================================================================
-- Este script define la estructura de las tablas en la base de datos PostgreSQL.
-- Sigue un enfoque de "event sourcing" y datos derivados, inspirado en los
-- principios de "Designing Data-Intensive Applications".

-- =============================================================================
--  Tabla 1: propiedades
-- =============================================================================
-- Almacena las propiedades únicas que hemos encontrado. Actúa como nuestra
-- tabla de "dimensiones" o entidades principales. El link es la clave natural
-- que garantiza que no dupliquemos propiedades.
--
CREATE TABLE propiedades (
    id SERIAL PRIMARY KEY,
    link TEXT NOT NULL UNIQUE,
    titulo TEXT,
    ubicacion TEXT,
    fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);

COMMENT ON TABLE propiedades IS 'Tabla de entidades para propiedades únicas, identificadas por su URL.';
COMMENT ON COLUMN propiedades.link IS 'URL única de la propiedad. Actúa como clave natural.';


-- =============================================================================
--  Tabla 2: observaciones_venta
-- =============================================================================
-- Este es nuestro "Log de Eventos". Cada fila representa una observación
-- inmutable de una propiedad en un momento específico. Nunca actualizamos filas
-- aquí, solo insertamos nuevas observaciones. Esto nos da un historial completo.
--
CREATE TABLE observaciones_venta (
    id SERIAL PRIMARY KEY,
    propiedad_id INTEGER NOT NULL REFERENCES propiedades(id) ON DELETE CASCADE,
    fecha_observacion TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    
    -- Almacenamos ambos valores para flexibilidad
    precio_clp BIGINT,
    precio_uf NUMERIC(10, 2), -- NUMERIC es ideal para valores monetarios
    
    superficie_util_m2 NUMERIC(10, 2),
    dormitorios INTEGER,
    
    -- Datos adicionales para contexto
    atributos_raw TEXT,
    imagen_url TEXT,
    
    -- Flag para que el analizador sepa qué procesar
    es_nueva BOOLEAN DEFAULT TRUE
);

COMMENT ON TABLE observaciones_venta IS 'Log inmutable de todas las observaciones de propiedades. La fuente de la verdad.';
COMMENT ON COLUMN observaciones_venta.propiedad_id IS 'FK a la propiedad a la que pertenece esta observación.';
COMMENT ON COLUMN observaciones_venta.es_nueva IS 'Flag para indicar si esta observación ya fue procesada por el analizador.';


-- =============================================================================
--  Tabla 3: metricas_historicas
-- =============================================================================
-- Esta tabla almacena "Datos Derivados". Los valores aquí son calculados
-- por el script analizador a partir de los datos en `observaciones_venta`.
-- Si esta tabla se corrompe o se borra, puede ser reconstruida completamente
-- a partir del log de observaciones.
--
CREATE TABLE metricas_historicas (
    id SERIAL PRIMARY KEY,
    observacion_id INTEGER NOT NULL REFERENCES observaciones_venta(id) ON DELETE CASCADE,
    fecha_calculo TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    uf_por_m2 NUMERIC(10, 2)
);

COMMENT ON TABLE metricas_historicas IS 'Datos derivados. Almacena métricas calculadas como UF/m2.';
COMMENT ON COLUMN metricas_historicas.observacion_id IS 'FK a la observación que originó este cálculo, para trazabilidad.';


-- =============================================================================
--  Tabla 4: log_ejecucion
-- =============================================================================
-- Tabla de operabilidad para monitorear la salud de nuestros scripts.
-- Registra cada ejecución, su estado y posibles errores.
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


-- =============================================================================
--  Índices para mejorar el rendimiento de las consultas
-- =============================================================================

-- Índice para buscar rápidamente observaciones de una propiedad específica.
CREATE INDEX idx_observaciones_propiedad_id ON observaciones_venta(propiedad_id);

-- Índice parcial. Es muy eficiente porque solo indexa las filas que el
-- analizador necesita procesar (las que no han sido procesadas aún).
CREATE INDEX idx_observaciones_nuevas ON observaciones_venta(id) WHERE es_nueva = TRUE;

-- Índice para buscar la última ejecución de un script específico en el monitor.
CREATE INDEX idx_log_script_tiempo ON log_ejecucion(script_name, start_time DESC);

-- PostgreSQL crea automáticamente un índice para la restricción UNIQUE en `propiedades.link`.

-- =============================================================================
--  Fin del Script
-- =============================================================================