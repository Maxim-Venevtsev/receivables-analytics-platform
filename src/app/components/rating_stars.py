def rating_color(stars: int | None) -> str:
    colors = {
        5: "#fbbf24",  # gold
        4: "#f59e0b",  # warm yellow
        3: "#eab308",  # neutral yellow
        2: "#f97316",  # orange
        1: "#ea580c",  # red-orange
    }

    if stars is None:
        return "#9ca3af"

    return colors.get(int(stars), "#9ca3af")


def rating_stars_html(stars: int | None) -> str:
    if stars is None:
        return "—"

    stars = int(stars)
    active_color = rating_color(stars)
    inactive_color = "#d1d5db"

    html = ""

    for i in range(1, 6):
        if i <= stars:
            html += f'<span style="color:{active_color};">★</span>'
        else:
            html += f'<span style="color:{inactive_color};">☆</span>'

    return html


def rating_aggrid_cell_renderer() -> str:
    return """
        params => {
            const stars = params.value;

            if (stars === null || stars === undefined) {
                return '<span style="color:#9ca3af;">—</span>';
            }

            const colors = {
                5: '#fbbf24',
                4: '#f59e0b',
                3: '#eab308',
                2: '#f97316',
                1: '#ea580c',
            };

            const activeColor = colors[stars] || '#9ca3af';
            const inactiveColor = '#d1d5db';

            let html = '';

            for (let i = 1; i <= 5; i++) {
                if (i <= stars) {
                    html += `<span style="color:${activeColor};">★</span>`;
                } else {
                    html += `<span style="color:${inactiveColor};">☆</span>`;
                }
            }

            return `<span style="font-size:16px; font-weight:600;">${html}</span>`;
        }
    """