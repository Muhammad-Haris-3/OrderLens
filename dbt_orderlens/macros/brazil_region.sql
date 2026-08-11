{#
    Map a two-letter Brazilian state code to its macro-region.

    A macro rather than a repeated CASE: the mapping is needed by dim_geography,
    dim_customers and dim_sellers, and three copies of a 27-way branch is three
    places for one state to end up in the wrong region. Segmentation by region is
    a BQ-4 deliverable, so a misfiled state moves money in the final ranking.

    The five regions are IBGE's official grouping. 'unknown' is reachable only if
    a state code appears that A-06/A-22 did not see — in which case the
    accepted_values test on state fires first and says so.
#}

{% macro brazil_region(state_column) %}
    case upper({{ state_column }})
        when 'AC' then 'Norte'
        when 'AP' then 'Norte'
        when 'AM' then 'Norte'
        when 'PA' then 'Norte'
        when 'RO' then 'Norte'
        when 'RR' then 'Norte'
        when 'TO' then 'Norte'

        when 'AL' then 'Nordeste'
        when 'BA' then 'Nordeste'
        when 'CE' then 'Nordeste'
        when 'MA' then 'Nordeste'
        when 'PB' then 'Nordeste'
        when 'PE' then 'Nordeste'
        when 'PI' then 'Nordeste'
        when 'RN' then 'Nordeste'
        when 'SE' then 'Nordeste'

        when 'DF' then 'Centro-Oeste'
        when 'GO' then 'Centro-Oeste'
        when 'MT' then 'Centro-Oeste'
        when 'MS' then 'Centro-Oeste'

        when 'ES' then 'Sudeste'
        when 'MG' then 'Sudeste'
        when 'RJ' then 'Sudeste'
        when 'SP' then 'Sudeste'

        when 'PR' then 'Sul'
        when 'RS' then 'Sul'
        when 'SC' then 'Sul'

        else 'unknown'
    end
{% endmacro %}
