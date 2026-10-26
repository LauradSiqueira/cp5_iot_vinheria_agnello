from dash import Dash, html

app = Dash(__name__)
app.layout = html.H1("Vinheria - dashboard funcionando")

if __name__ == "__main__":
    app.run(debug=True)