
# 🏙️ Urban QoL Scorer & Real Estate Analyzer

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://krakow-ocena.streamlit.app/)

## 📌 Project Overview
An advanced GIS analytics tool designed to evaluate the Quality of Life (QoL) and attractiveness of urban neighborhoods loosely based on the "15-minute city" concept.

The model utilizes the Uber H3 hexagonal grid to aggregate thousands of spatial data points across Krakow, calculating a comprehensive **Livability Score**. The evaluation factors in green areas, daily infrastructure, education, public transport accessibility, and space-degrading elements (noise, industrial zones). This score is then cross-referenced with local real estate prices to accurately identify undervalued investment opportunities.

## 💼 Business Value
* **Urban Planning:** Objective measurement of neighborhood quality and identification of infrastructure gaps (e.g., "transit deserts").
* **PropTech & Real Estate Investment:** Automated discovery of "investment gems" – locations with a high livability score but a price per square meter below the market median (*Value Ratio*).
* **Transport Reliability:** The engine processes raw GTFS schedules to calculate actual transfer-free transit reachability, heavily rewarding reliable rail communication (trams).

## 💡 Key Urban & Business Insights
* **The "Prestige Trap" (Wola Justowska):** High real estate prices do not always correlate with a high Quality of Life score. Premium locations often suffer from poor urban infrastructure, lacking basic walkability and POI density.
* **The "Communist-Era" Urban Efficiency:** Older residential districts (like Nowa Huta or large-panel system blocks) naturally score very high in the 15-minute city framework due to centrally planned infrastructure (schools, parks, transport), making them highly undervalued on the real estate market.

## 🚀 Engineering Architecture & Optimizations
Processing millions of spatial relationships required shifting from standard scripts to optimized data pipelines:
* **Spatial Indexing (`sindex`):** Implemented a *Filter & Refine* pattern based on R-Trees. Pre-filtering data discards geometries outside the area of interest, reducing spatial query time by over 90%.
* **Native Coordinate Transformation:** Replaced computationally heavy `GeoSeries` objects inside loops with a global, pure-math `pyproj.Transformer` instance. This achieved a 30x speedup in coordinate translation (from 119 µs to ~3 µs per operation).
* **Distance Decay Functions:** Deployed non-linear, continuous distance decay functions – objects closer to the hexagon center receive higher scores, accurately simulating pedestrian willingness to travel.

## 🛠️ Tech Stack
* **Geospatial & Big Data:** `GeoPandas`, `Shapely`, `h3-py`, `pyproj`
* **Data Manipulation:** `Pandas`, `NumPy`
* **Frontend & Visualization:** `Streamlit`, `Folium`, `streamlit-folium`

## 🗺️ Core Application Modules
1. **Macro View (H3 Grid):** An interactive city-wide map for analyzing the score distribution and finding areas with the best quality-to-price ratio.
2. **Micro View (Place Rating):** A dynamically generated analytics panel for a selected point. It breaks down the final score into its core components, visualizing individual layers (greenery, transport, amenities) on a precise local map.


## 💻 Installation & Local Setup

To run this project locally, it is highly recommended to use a virtual environment. This ensures that heavy geospatial dependencies (like `GeoPandas` and `pyproj`) do not conflict with your global Python installation.

**1. Clone the repository**
```bash
git clone https://github.com/i-slusarczyk/urban-qol-scorer.git
cd urban-qol-scorer
```

**2. Create and activate a virtual environment**
* **Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```
* **macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Run the Streamlit application**
```bash
streamlit run main.py
```

## 🚧 Roadmap / Version 2.0
This project is under active development. Upcoming iterations will include:
* **Public Transport Expansion:** Extending GTFS processing capabilities to encompass additional transit modes, including metro lines and trolleybuses, ensuring robust scalability across diverse metropolitan areas.
* **Isochrone Analysis:** Replacing simple radial buffers with true pedestrian and cycling isochrones, accounting for the street network and architectural barriers.
* **Real Estate Transaction Registry:** Integrating official government transaction data (RCiWN) instead of portal listing prices to increase the precision of the *Value Ratio*.
* **Enhanced UI:** Replacing standard point markers with categorized, custom POI icons in the *Micro View*.
* **Memory Management (Downcasting):** Implementing strict numeric downcasting in Pandas to optimize RAM usage, enabling seamless scaling of the model to entire metropolitan areas and regions.


## 📚 Sources & Methodology
The analytical methodology, scoring mechanics, and datasets utilized in this project are strictly grounded in the following research papers, urban reports, and data sources:

* Boeing, G. (2025). Modeling and analyzing urban networks and amenities with OSMnx. *Geographical Analysis*. Advance online publication. https://doi.org/10.1111/gean.70009
* Chrzanowski, M. (2024). *Barometr Krakowski 2024: Raport badawczy – badanie społeczne jakości życia oraz jakości usług publicznych w Krakowie*. Urząd Miasta Krakowa. https://strategia.krakow.pl/barometr-krakowski/287916,artykul,edycja-2024.html
* Czerniak, A., & Jarczewska-Gerc, E. (2023). *Szczęśliwy dom: Badanie dobrostanu mieszkańców Polski 2023*. Otodom; Polityka Insight; Uniwersytet SWPS. https://www.otodom.pl/wiadomosci/pobierz/raporty/szczesliwy-dom-badanie-dobrostanu-mieszkancow-polski-2023
* Jamróz, K. (2024). *Apartment Prices in Poland* [Data set]. Kaggle. https://www.kaggle.com/datasets/krzysztofjamroz/apartment-prices-in-poland
* Saaty, T. L. (1980). *The Analytic Hierarchy Process: Planning, priority setting, resource allocation*. McGraw-Hill. https://doi.org/10.21236/ADA214804
