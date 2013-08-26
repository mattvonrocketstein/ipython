{#

DO NOT USE THIS AS A BASE WORK,
IF YOU ARE COPY AND PASTING THIS FILE
YOU ARE PROBABLY DOING THINGS WRONG.

Null template, Does nothing except defining a basic structure
To layout the different blocks of a notebook.

Subtemplates can override blocks to define their custom representation.

If one of the block you do overwrite is not a leave block, consider
calling super.

{%- block nonLeaveBlock -%}
    #add stuff at beginning
    {{ super() }}
    #add stuff at end
{%- endblock nonLeaveBlock -%}

consider calling super even if it is a leave block, we might insert more blocks later.

#}
{%- block header -%}
{%- endblock header -%}
{%- block body -%}
{%- for worksheet in nb.worksheets -%}
    {%- for cell in worksheet.cells -%}
        {%- block any_cell scoped -%}
            {%- if cell.cell_type in ['code'] -%}
                {%- block codecell scoped -%}
                    {%- block input_group -%}
                        {%- include 'cell_input.tpl' -%}
                    {%- endblock input_group -%}
                    {%- if cell.outputs -%}
                    {%- block output_group -%}
                        {%- include 'cell_outputs.tpl' -%}
                    {%- endblock output_group -%}
                    {%- endif -%}
                {%- endblock codecell -%}
            {%- elif cell.cell_type in ['markdown'] -%}
                {%- block markdowncell scoped-%}
                {%- endblock markdowncell -%}
            {%- elif cell.cell_type in ['heading'] -%}
                {%- block headingcell scoped-%}
                {%- endblock headingcell -%}
            {%- elif cell.cell_type in ['raw'] -%}
                {%- block rawcell scoped-%}
                {%- endblock rawcell -%}
            {%- else -%}
                {%- block unknowncell scoped-%}
                {%- endblock unknowncell -%}
            {%- endif -%}
        {%- endblock any_cell -%}
    {%- endfor -%}
{%- endfor -%}
{%- endblock body -%}

{%- block footer -%}
{%- endblock footer -%}
