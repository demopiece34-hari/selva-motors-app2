import json
from pathlib import Path

import streamlit as st

# ============================================================
# HERO BIKES / SCOOTERS CATALOG
# English + Thanglish only
# Local photo support + full specifications + BikeWale links
# ============================================================

ASSET_DIR = Path(__file__).resolve().parent / "assets" / "hero_bikes"


def _t(lang: str, key: str) -> str:
    pack = {
        "English": {
            "title": "Hero Bikes & Scooters",
            "subtitle": "Browse current Hero two-wheelers with English / Thanglish support, photos, colors, and full specifications.",
            "search": "Search model",
            "category": "Category",
            "all": "All",
            "scooter": "Scooter",
            "motorcycle": "Motorcycle",
            "show_full": "Show full specifications",
            "open_official": "Open official page",
            "open_bikewale": "Open BikeWale",
            "image": "Photo",
            "colors": "Colors",
            "features": "Features",
            "specifications": "Specifications",
            "no_match": "No models matched your search.",
            "export": "Download catalog JSON",
            "source_note": "Starter set based on official Hero pages and BikeWale model pages. Add more models the same way.",
            "compare": "Quick compare",
            "clear": "Clear filters",
            "price_note": "Price / availability can change by city.",
        },
        "Thanglish": {
            "title": "Hero Bikes & Scooters",
            "subtitle": "Current Hero models-a English / Thanglish support oda photo, color, full specification oda browse pannunga.",
            "search": "Model thedu",
            "category": "Category",
            "all": "Ellaam",
            "scooter": "Scooter",
            "motorcycle": "Bike",
            "show_full": "Full specifications kaattu",
            "open_official": "Official page open pannunga",
            "open_bikewale": "BikeWale open pannunga",
            "image": "Photo",
            "colors": "Colors",
            "features": "Features",
            "specifications": "Specifications",
            "no_match": "Search-ku match aana model illa.",
            "export": "Catalog JSON download pannunga",
            "source_note": "Current lineup starter set official Hero pages + BikeWale model pages base pannina data. Idhe style-la innum models add pannalaam.",
            "compare": "Quick compare",
            "clear": "Filters clear pannunga",
            "price_note": "Price / availability city-ku city change aagalam.",
        },
    }
    return pack.get(lang, pack["English"]).get(key, key)


def _pick(lang: str, data: dict, fallback: str = "") -> str:
    return data.get(lang) or data.get("English") or fallback


def _match(model: dict, query: str, category: str) -> bool:
    if category != "All" and model["category"] != category:
        return False
    q = (query or "").strip().lower()
    if not q:
        return True
    blob = " ".join(
        [
            model["name"],
            model["category"],
            model.get("engine_cc", ""),
            model.get("summary", {}).get("English", ""),
            model.get("summary", {}).get("Thanglish", ""),
            " ".join(model.get("colors", [])),
            " ".join(model.get("features", {}).get("English", [])),
            " ".join(model.get("features", {}).get("Thanglish", [])),
            " ".join(model.get("spec_sections", {}).keys()),
        ]
    ).lower()
    return q in blob


def _image_source(model: dict):
    image = model.get("image", "")
    if not image:
        return None
    if image.startswith("http://") or image.startswith("https://"):
        return image
    p = Path(image)
    if not p.is_absolute():
        p = ASSET_DIR / image
    return str(p) if p.exists() else None


def _bike_card(model: dict, lang: str, show_full: bool):
    image_src = _image_source(model)
    official_url = model.get("official_url", "")
    bikewale_url = model.get("bikewale_url", "")

    st.markdown(
        """
        <style>
        .hero-bikes-hero {
            padding: 18px 20px;
            border-radius: 24px;
            background: linear-gradient(135deg, #111827, #e31837);
            color: #fff;
            margin-bottom: 16px;
            box-shadow: 0 18px 42px rgba(17,24,39,.18);
        }
        .hero-bikes-hero h1 { margin: 0; font-size: 30px; font-weight: 900; letter-spacing: -.6px; }
        .hero-bikes-hero p { margin: 7px 0 0 0; color: #fecdd3; font-weight: 700; }
        .bike-shell {
            background: #fff;
            border: 1px solid #e2e8f0;
            border-radius: 22px;
            padding: 16px;
            box-shadow: 0 14px 34px rgba(15,23,42,.08);
            height: 100%;
        }
        .bike-name { margin: 0; font-size: 20px; font-weight: 900; color: #0f172a; }
        .bike-sub { color: #64748b; font-weight: 700; margin-top: 4px; }
        .chip {
            display:inline-block;
            padding: 5px 10px;
            border-radius: 999px;
            background: #fff1f2;
            color: #be123c;
            border: 1px solid #fecdd3;
            font-size: 12px;
            font-weight: 800;
            margin: 0 6px 6px 0;
        }
        .spec-row {
            display:flex;
            gap:12px;
            justify-content:space-between;
            border-bottom: 1px dashed #e2e8f0;
            padding: 7px 0;
        }
        .spec-row:last-child { border-bottom: 0; }
        .spec-k { color:#64748b; font-weight:700; font-size: 13px; }
        .spec-v { color:#0f172a; font-weight:900; font-size: 13px; text-align:right; }
        .mini-note { color:#64748b; font-size:12px; margin-top: 8px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='bike-shell'>", unsafe_allow_html=True)
    st.markdown(f"<div class='bike-name'>{model['name']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='bike-sub'>{model['category']} • {model.get('engine_cc','')}</div>", unsafe_allow_html=True)
    st.write(_pick(lang, model.get("summary", {})))

    if image_src:
        st.image(image_src, use_container_width=True)
    else:
        st.info(f"{_t(lang, 'image')}: {model.get('image_note', 'Add a photo file in assets/hero_bikes/')}")
        st.caption(model.get("image_note", "Add a photo file in assets/hero_bikes/"))

    st.markdown(f"**{_t(lang, 'colors')}**")
    for c in model.get("colors", []):
        st.markdown(f"<span class='chip'>{c}</span>", unsafe_allow_html=True)

    st.markdown(f"**{_t(lang, 'features')}**")
    for feat in model.get("features", {}).get(lang, model.get("features", {}).get("English", [])):
        st.write(f"• {feat}")

    if official_url:
        st.link_button(_t(lang, "open_official"), official_url, use_container_width=True)
    if bikewale_url:
        st.link_button(_t(lang, "open_bikewale"), bikewale_url, use_container_width=True)

    st.caption(_t(lang, "price_note"))

    if show_full:
        for sec_name, rows in model.get("spec_sections", {}).items():
            with st.expander(sec_name, expanded=False):
                for k, v in rows.items():
                    st.markdown(
                        f"""
                        <div class='spec-row'>
                            <div class='spec-k'>{k}</div>
                            <div class='spec-v'>{v}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    st.markdown(f"<div class='mini-note'>{_t(lang, 'source_note')}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


BIKES = [
    {
        "name": "HF Deluxe",
        "category": "Motorcycle",
        "engine_cc": "97.2 cc",
        "image": "hf_deluxe.jpg",
        "image_note": "Place a photo file named hf_deluxe.jpg inside assets/hero_bikes/",
        "official_url": "https://www.heromotocorp.com/en-in/motorcycles/practical/hf-deluxe.html",
        "bikewale_url": "https://www.bikewale.com/hero-bikes/hf-deluxe/",
        "summary": {
            "English": "A practical commuter built for daily mileage and low running cost.",
            "Thanglish": "Daily mileage and low running cost-ku practical commuter bike.",
        },
        "colors": ["Blue Black", "Red Black", "Candy Blazing Red", "Black Nexus Blue", "Sports Red Black"],
        "features": {
            "English": ["Fuel-efficient daily commuter", "Simple, reliable and easy to maintain", "Comfortable city and village use"],
            "Thanglish": ["Fuel-efficient daily commuter", "Simple-a maintain panna easy", "City-um village-um comfortable use"],
        },
        "spec_sections": {
            "Power & Performance": {
                "Displacement": "97.2 cc",
                "Max Power": "7.91 bhp @ 8000 rpm",
                "Max Torque": "8.05 Nm @ 6000 rpm",
                "Top Speed": "87 kmph",
                "Mileage - Owner Reported": "62 kmpl",
                "Transmission": "4 Speed Manual",
                "Transmission Type": "Chain Drive",
                "Gear Shifting Pattern": "All 4 Up",
                "Clutch": "Wet Multiplate",
                "Riding Range": "607.6 km",
                "Riding Modes": "No",
                "Engine Type": "1 Cylinder, Air Cooled, 2 Valves",
                "Bore x Stroke": "50 mm x 49.5 mm",
                "Compression Ratio": "9.9:1",
                "Spark Plugs": "1 Per Cylinder",
                "Battery": "MF Battery, 12V - 3Ah",
                "Emission Standard": "BS6 Phase 2B",
                "Fuel Type": "Petrol",
            },
            "Brakes & Wheels": {
                "Braking System": "IBS",
                "Front Brake": "Drum, 130 mm",
                "Rear Brake": "Drum, 130 mm",
                "Wheel Type": "Alloy",
                "Wheel Size": "Front - 18 inch, Rear - 18 inch",
                "Tyre Size": "Front - 80/100 - 18, Rear - 80/100 - 18",
                "Tyre Type": "Tubeless",
                "Tyre Pressure (Rider Only)": "Front - 25 psi, Rear - 28 psi",
                "Tyre Pressure (Rider & Pillion)": "Front - 25 psi, Rear - 41 psi",
            },
            "Suspensions & Chassis": {
                "Front Suspension": "Telescopic Hydraulic Shock Absorbers",
                "Rear Suspension": "5-step Adjustable Hydraulic Shock Absorbers",
                "Front Suspension Preload Adjuster": "No",
                "Rear Suspension Preload Adjuster": "Yes",
                "Chassis Type": "Tubular Double Cradle",
            },
            "Dimensions": {
                "Kerb Weight": "112 kg",
                "Seat Height": "785 mm",
                "Seat Length": "-",
                "Ground Clearance": "165 mm",
            },
            "Warranty and Services": {
                "Vehicle Warranty": "70,000 km or 5 years",
                "No. of Free Services": "5",
                "1st Service": "500-750 km or 60 days",
                "2nd Service": "3000-3500 km or 160 days",
                "3rd Service": "6000-6500 km or 260 days",
                "4th Service": "9000-9500 km or 360 days",
                "5th Service": "12000-12500 km or 460 days",
            },
            "Features": {
                "Instrument Console": "Analogue",
                "Mobile Phone Connectivity": "No",
                "GPS & Navigation": "No",
                "Average Fuel Consumption": "No",
            },
            "Safety & Convenience": {
                "USB Charging Port": "No",
                "Keyless Lock/Unlock": "No",
                "Saree Guard": "Yes",
                "Quickshifter": "No",
            },
            "Mobile App Monitoring": {
                "Vehicle Location Tracking": "No",
                "Geo Fencing": "No",
            },
            "Lights": {
                "Headlight": "Halogen Headlamp",
                "DRLs (Daytime Running Lights)": "Yes",
                "Brake/Tail Light": "Halogen Bulb",
                "Hazard Warning Lights": "No",
            },
            "Seat & Storage": {
                "Under Seat Storage": "No",
                "Pillion Seat": "Yes",
                "Pillion Comfort": "Footrest, Grab rail",
            },
            "Additional Features": {
                "Additional Features": "XSENS Advantage Technology",
            },
        },
    },
    {
        "name": "Splendor Plus",
        "category": "Motorcycle",
        "engine_cc": "97.2 cc",
        "image": "splendor_plus.jpg",
        "image_note": "Place a photo file named splendor_plus.jpg inside assets/hero_bikes/",
        "official_url": "https://www.heromotocorp.com/en-in/motorcycles/practical/splendor-plus.html",
        "bikewale_url": "https://www.bikewale.com/hero-bikes/splendor-plus/",
        "summary": {
            "English": "Hero's classic commuter with trusted mileage and daily usability.",
            "Thanglish": "Trusted mileage and daily usability oda classic commuter.",
        },
        "colors": ["Black", "Silver", "Red", "Blue", "Grey"],
        "features": {
            "English": ["Trusted commuter platform", "Easy maintenance", "Popular daily ride"],
            "Thanglish": ["Trusted commuter platform", "Easy maintenance", "Popular daily ride"],
        },
        "spec_sections": {
            "Power & Performance": {
                "Displacement": "97.2 cc",
                "Max Power": "7.91 bhp @ 8000 rpm",
                "Max Torque": "8.05 Nm @ 6000 rpm",
                "Transmission": "4 Speed Manual",
                "Mileage - Owner Reported": "62 kmpl",
                "Clutch": "Wet Multiplate",
                "Fuel Type": "Petrol",
                "Engine Type": "Air Cooled, Single Cylinder",
            },
            "Dimensions": {
                "Kerb Weight": "112 kg",
                "Ground Clearance": "175 mm",
                "Seat Height": "785 mm",
            },
            "Warranty and Services": {
                "Vehicle Warranty": "70,000 km or 5 years",
                "No. of Free Services": "5",
            },
            "Safety & Convenience": {
                "Saree Guard": "Yes",
                "USB Charging Port": "No",
                "Keyless Lock/Unlock": "No",
            },
        },
    },
    {
        "name": "Passion Plus",
        "category": "Motorcycle",
        "engine_cc": "97.2 cc",
        "image": "passion_plus.jpg",
        "image_note": "Place a photo file named passion_plus.jpg inside assets/hero_bikes/",
        "official_url": "https://www.heromotocorp.com/en-in/motorcycles/practical/passion-plus.html",
        "bikewale_url": "https://www.bikewale.com/hero-bikes/passion-plus/",
        "summary": {
            "English": "A commuter bike with comfortable ride, good mileage and practical features.",
            "Thanglish": "Comfortable ride, good mileage, practical features oda commuter bike.",
        },
        "colors": ["Black Grey", "Sports Red", "Heavy Grey", "Nexus Blue", "Candy Blazing Red"],
        "features": {
            "English": ["Reliable daily use", "Comfort-oriented riding", "Practical commuter design"],
            "Thanglish": ["Reliable daily use", "Comfort-oriented riding", "Practical commuter design"],
        },
        "spec_sections": {
            "Power & Performance": {
                "Displacement": "97.2 cc",
                "Max Power": "7.91 bhp @ 8000 rpm",
                "Max Torque": "8.05 Nm @ 6000 rpm",
                "Transmission": "4 Speed Manual",
                "Mileage - Owner Reported": "62 kmpl",
                "Clutch": "Wet Multiplate",
                "Fuel Type": "Petrol",
            },
            "Dimensions": {
                "Kerb Weight": "115 kg",
                "Fuel Tank": "11 litres",
            },
            "Warranty and Services": {
                "Vehicle Warranty": "70,000 km or 5 years",
                "No. of Free Services": "5",
            },
            "Features": {
                "Instrument Console": "Analogue",
                "Mobile Phone Connectivity": "No",
                "GPS & Navigation": "No",
            },
            "Safety & Convenience": {
                "Saree Guard": "Yes",
                "USB Charging Port": "No",
                "Quickshifter": "No",
            },
        },
    },
    {
        "name": "Super Splendor XTEC",
        "category": "Motorcycle",
        "engine_cc": "124.7 cc",
        "image": "super_splendor_xtec.jpg",
        "image_note": "Place a photo file named super_splendor_xtec.jpg inside assets/hero_bikes/",
        "official_url": "https://www.heromotocorp.com/en-in/motorcycles/executive/super-splendor-xtec.html",
        "bikewale_url": "https://www.bikewale.com/hero-bikes/super-splendor-xtec/",
        "summary": {
            "English": "A practical 125 cc commuter with digital console and strong daily usability.",
            "Thanglish": "Digital console oda strong daily usability கொண்ட practical commuter bike.",
        },
        "colors": ["Black", "Nexus Blue", "Candy Blazing Red", "Silver"],
        "features": {
            "English": ["Digital console", "Commuter friendly", "Balanced ride quality"],
            "Thanglish": ["Digital console", "Commuter friendly", "Balanced ride quality"],
        },
        "spec_sections": {
            "Power & Performance": {
                "Displacement": "124.7 cc",
                "Max Power": "10.72 bhp",
                "Max Torque": "10.6 Nm",
                "Transmission": "4 Speed Manual",
                "Fuel Type": "Petrol",
            },
            "Dimensions": {
                "Kerb Weight": "122 kg",
                "Fuel Tank": "12 litres",
            },
        },
    },
    {
        "name": "HF Deluxe Flex Fuel",
        "category": "Motorcycle",
        "engine_cc": "97.2 cc",
        "image": "hf_deluxe_flex_fuel.jpg",
        "image_note": "Place a photo file named hf_deluxe_flex_fuel.jpg inside assets/hero_bikes/",
        "official_url": "https://www.heromotocorp.com/en-in/motorcycles/practical/hf-deluxe.html",
        "bikewale_url": "https://www.bikewale.com/hero-bikes/hf-deluxe-flex-fuel/",
        "summary": {
            "English": "A fuel-friendly commuter version with the same practical HF family feel.",
            "Thanglish": "Fuel-friendly commuter version with practical HF family feel.",
        },
        "colors": ["Black Red", "Black Blue", "Grey"],
        "features": {
            "English": ["Commuter practical design", "Fuel-friendly family bike", "Easy maintenance"],
            "Thanglish": ["Commuter practical design", "Fuel-friendly family bike", "Easy maintenance"],
        },
        "spec_sections": {
            "Power & Performance": {
                "Displacement": "97.2 cc",
                "Max Power": "7.91 bhp @ 8000 rpm",
                "Max Torque": "8.05 Nm @ 6000 rpm",
                "Fuel Type": "Petrol / Flex Fuel variant",
            }
        },
    },
    {
        "name": "Destini 110",
        "category": "Scooter",
        "engine_cc": "110 cc",
        "image": "destini_110.jpg",
        "image_note": "Place a photo file named destini_110.jpg inside assets/hero_bikes/",
        "official_url": "https://www.heromotocorp.com/en-in/scooters/destini-110.html",
        "bikewale_url": "",
        "summary": {
            "English": "A comfortable family scooter for daily commuting.",
            "Thanglish": "Daily commute-ku comfortable family scooter.",
        },
        "colors": ["See official page for current colour options"],
        "features": {
            "English": ["Practical family scooter", "Smooth city ride focus", "Good daily usability"],
            "Thanglish": ["Family use-ku nalla scooter", "City-la smooth ride", "Daily use-ku practical"],
        },
        "spec_sections": {"Power & Performance": {"Engine": "110 cc", "Fuel Type": "Petrol"}},
    },
    {
        "name": "New Destini 125",
        "category": "Scooter",
        "engine_cc": "125 cc",
        "image": "new_destini_125.jpg",
        "image_note": "Place a photo file named new_destini_125.jpg inside assets/hero_bikes/",
        "official_url": "https://www.heromotocorp.com/en-in/scooters/new-destini-125.html",
        "bikewale_url": "",
        "summary": {
            "English": "An elegant and practical 125 cc family scooter.",
            "Thanglish": "Elegant 125 cc family scooter.",
        },
        "colors": ["Candy Blazing Red", "Pearl Fadeless White", "Pearl Black"],
        "features": {
            "English": ["Smooth performance", "Practical commuting", "Modern styling"],
            "Thanglish": ["Smooth performance", "Daily commuting-ku useful", "Modern look"],
        },
        "spec_sections": {"Power & Performance": {"Engine": "125 cc"}},
    },
    {
        "name": "Destini Prime",
        "category": "Scooter",
        "engine_cc": "124.6 cc",
        "image": "destini_prime.jpg",
        "image_note": "Place a photo file named destini_prime.jpg inside assets/hero_bikes/",
        "official_url": "https://www.heromotocorp.com/en-in/scooters/destini-prime.html",
        "bikewale_url": "",
        "summary": {
            "English": "A refined scooter for comfortable everyday riding.",
            "Thanglish": "Comfortable everyday riding-ku refined scooter.",
        },
        "colors": ["See official page for latest colour options"],
        "features": {
            "English": ["Daily commute friendly", "Comfort-oriented", "Refined performance"],
            "Thanglish": ["Daily commute-friendly", "Comfort focus", "Refined performance"],
        },
        "spec_sections": {"Power & Performance": {"Engine": "124.6 cc"}},
    },
    {
        "name": "Xoom 110",
        "category": "Scooter",
        "engine_cc": "110.9 cc",
        "image": "xoom_110.jpg",
        "image_note": "Place a photo file named xoom_110.jpg inside assets/hero_bikes/",
        "official_url": "https://www.heromotocorp.com/en-in/scooters/xoom.html",
        "bikewale_url": "",
        "summary": {
            "English": "A sporty scooter with sharp styling and smart features.",
            "Thanglish": "Sharp styling and smart features oda sporty scooter.",
        },
        "colors": ["Black", "Polestar Blue", "Moon Yellow"],
        "features": {
            "English": ["Sporty design", "Smart features", "Fun city ride"],
            "Thanglish": ["Sporty design", "Smart features", "City ride fun-a irukkum"],
        },
        "spec_sections": {"Power & Performance": {"Engine": "110.9 cc"}},
    },
    {
        "name": "Xoom 125",
        "category": "Scooter",
        "engine_cc": "124.6 cc",
        "image": "xoom_125.jpg",
        "image_note": "Place a photo file named xoom_125.jpg inside assets/hero_bikes/",
        "official_url": "https://www.heromotocorp.com/en-in/scooters/xoom-125.html",
        "bikewale_url": "",
        "summary": {
            "English": "A sporty 125 cc scooter with quick response.",
            "Thanglish": "Quick response kudukkura sporty 125 cc scooter.",
        },
        "colors": ["Matte Grey", "Vibrant Blue Metallic"],
        "features": {
            "English": ["Quick acceleration", "Smart features", "Stylish design"],
            "Thanglish": ["Quick acceleration", "Smart features", "Stylish design"],
        },
        "spec_sections": {"Power & Performance": {"Engine": "124.6 cc"}},
    },
    {
        "name": "Xoom 160",
        "category": "Scooter",
        "engine_cc": "156 cc",
        "image": "xoom_160.jpg",
        "image_note": "Place a photo file named xoom_160.jpg inside assets/hero_bikes/",
        "official_url": "https://www.heromotocorp.com/en-in.html",
        "bikewale_url": "",
        "summary": {
            "English": "A premium sporty scooter in the Xoom family.",
            "Thanglish": "Xoom family-la premium sporty scooter.",
        },
        "colors": ["See official page for current colour options"],
        "features": {
            "English": ["Premium sporty feel", "High engine capacity", "Modern styling"],
            "Thanglish": ["Premium sporty feel", "High engine capacity", "Modern styling"],
        },
        "spec_sections": {"Power & Performance": {"Engine": "156 cc"}},
    },
    {
        "name": "Pleasure+ XTEC",
        "category": "Scooter",
        "engine_cc": "110.9 cc",
        "image": "pleasure_plus_xtec.jpg",
        "image_note": "Place a photo file named pleasure_plus_xtec.jpg inside assets/hero_bikes/",
        "official_url": "https://www.heromotocorp.com/en-in/scooters/pleasure-plus-xtec.html",
        "bikewale_url": "",
        "summary": {
            "English": "A stylish scooter with commuter-friendly everyday use.",
            "Thanglish": "Commuter-friendly stylish scooter.",
        },
        "colors": ["See official page for latest colour options"],
        "features": {
            "English": ["Light and easy ride", "Daily city commuting", "Practical design"],
            "Thanglish": ["Light and easy ride", "Daily city commuting", "Practical design"],
        },
        "spec_sections": {"Power & Performance": {"Engine": "110.9 cc"}},
    },
    {
        "name": "Glamour",
        "category": "Motorcycle",
        "engine_cc": "125 cc",
        "image": "glamour.jpg",
        "image_note": "Place a photo file named glamour.jpg inside assets/hero_bikes/",
        "official_url": "https://www.heromotocorp.com/en-in/motorcycles/executive/glamour.html",
        "bikewale_url": "",
        "summary": {
            "English": "A reliable commuter with stylish everyday appeal.",
            "Thanglish": "Stylish everyday appeal oda reliable commuter.",
        },
        "colors": ["See official page for current colour options"],
        "features": {
            "English": ["Commuter friendly", "Stylish design", "Balanced performance"],
            "Thanglish": ["Commuter friendly", "Stylish design", "Balanced performance"],
        },
        "spec_sections": {"Power & Performance": {"Engine": "125 cc"}},
    },
    {
        "name": "Xtreme 125R",
        "category": "Motorcycle",
        "engine_cc": "125 cc",
        "image": "xtreme_125r.jpg",
        "image_note": "Place a photo file named xtreme_125r.jpg inside assets/hero_bikes/",
        "official_url": "https://www.heromotocorp.com/en-in/motorcycles/executive/xtreme-125r.html",
        "bikewale_url": "",
        "summary": {
            "English": "A sporty 125 cc motorcycle with quick acceleration.",
            "Thanglish": "Quick acceleration oda sporty 125 cc motorcycle.",
        },
        "colors": ["See official page for current colour options"],
        "features": {
            "English": ["5.7 sec 0-60 km/h acceleration", "Smart sporty styling", "Strong road presence"],
            "Thanglish": ["0-60 km/h 5.7 sec acceleration", "Smart sporty styling", "Road-la strong presence"],
        },
        "spec_sections": {
            "Power & Performance": {
                "Displacement": "125 cc",
                "Power": "11.4 BHP @ 8250 RPM",
                "Torque": "10.5 Nm @ 6500 RPM",
                "Acceleration": "5.7 sec (0-60 km/h)",
            }
        },
    },
    {
        "name": "Karizma XMR",
        "category": "Motorcycle",
        "engine_cc": "210 cc",
        "image": "karizma_xmr.jpg",
        "image_note": "Place a photo file named karizma_xmr.jpg inside assets/hero_bikes/",
        "official_url": "https://www.heromotocorp.com/en-in/motorcycles.html",
        "bikewale_url": "",
        "summary": {
            "English": "A sporty premium motorcycle in the Hero range.",
            "Thanglish": "Hero range-la sporty premium motorcycle.",
        },
        "colors": ["See official page for current colour options"],
        "features": {
            "English": ["Sporty premium design", "Control-focused ride", "Racing-inspired feel"],
            "Thanglish": ["Sporty premium design", "Control-focused ride", "Racing-inspired feel"],
        },
        "spec_sections": {"Power & Performance": {"Engine": "210 cc class"}},
    },
    {
        "name": "Xtreme 250R",
        "category": "Motorcycle",
        "engine_cc": "250 cc",
        "image": "xtreme_250r.jpg",
        "image_note": "Place a photo file named xtreme_250r.jpg inside assets/hero_bikes/",
        "official_url": "https://www.heromotocorp.com/en-in/motorcycles.html",
        "bikewale_url": "",
        "summary": {
            "English": "A performance-oriented Hero motorcycle.",
            "Thanglish": "Performance-oriented Hero motorcycle.",
        },
        "colors": ["See official page for current colour options"],
        "features": {
            "English": ["Performance-oriented", "Sporty ride", "Premium look"],
            "Thanglish": ["Performance-oriented", "Sporty ride", "Premium look"],
        },
        "spec_sections": {"Power & Performance": {"Engine": "250 cc class"}},
    },
]


def page_hero_bikes():
    if "hero_bikes_lang" not in st.session_state:
        st.session_state["hero_bikes_lang"] = "English"

    lang = st.sidebar.selectbox(
        "Language",
        ["English", "Thanglish"],
        key="hero_bikes_lang",
    )

    st.markdown(
        f"""
        <div class='hero-bikes-hero'>
            <h1>{_t(lang, 'title')}</h1>
            <p>{_t(lang, 'subtitle')}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        query = st.text_input(
            _t(lang, "search"),
            key="hero_bikes_search",
            placeholder="HF Deluxe / Splendor / Passion / Xoom",
        )
    with c2:
        cat_label = st.selectbox(
            _t(lang, "category"),
            [_t(lang, "all"), _t(lang, "scooter"), _t(lang, "motorcycle")],
            key="hero_bikes_category",
        )
    with c3:
        show_full = st.toggle(_t(lang, "show_full"), value=False, key="hero_bikes_toggle")

    cat_map = {
        _t(lang, "all"): "All",
        _t(lang, "scooter"): "Scooter",
        _t(lang, "motorcycle"): "Motorcycle",
    }
    category = cat_map.get(cat_label, "All")

    filtered = [b for b in BIKES if _match(b, query, category)]

    st.caption(_t(lang, "source_note"))
    st.caption(f"{_t(lang, 'compare')}: {len(filtered)} models")

    if not filtered:
        st.error(_t(lang, "no_match"))
        if st.button(_t(lang, "clear"), use_container_width=True):
            st.session_state["hero_bikes_search"] = ""
            st.session_state["hero_bikes_category"] = _t(lang, "all")
            st.rerun()
        return

    m1, m2, m3 = st.columns(3)
    m1.metric(_t(lang, "all"), len(filtered))
    m2.metric(_t(lang, "scooter"), len([b for b in filtered if b["category"] == "Scooter"]))
    m3.metric(_t(lang, "motorcycle"), len([b for b in filtered if b["category"] == "Motorcycle"]))

    for i in range(0, len(filtered), 2):
        cols = st.columns(2)
        for col, model in zip(cols, filtered[i:i+2]):
            with col:
                _bike_card(model, lang, show_full)

    st.divider()
    st.download_button(
        _t(lang, "export"),
        data=json.dumps(BIKES, ensure_ascii=False, indent=2),
        file_name="hero_bikes_catalog_en_th.json",
        mime="application/json",
        use_container_width=True,
    )


if __name__ == "__main__":
    page_hero_bikes()
