import streamlit as st

def inject_global_styles():
    """Calculates and injects global CSS for tabs and general layout."""
    st.markdown("""
        <style>
            /* 1. Global Tab Styling (Apply to Outer Tabs) */
            div[data-testid="stTabs"] button {
                gap: 30px; /* More space between tabs */
            }
            div[data-testid="stTabs"] button p {
                font-size: 16px !important; /* Smaller, cleaner font */
                font-weight: 500 !important;
            }
            
            /* 3. Color Overrides for ALL Tabs (Remove Red) */
            /* Selected Tab Text */
            div[data-testid="stTabs"] button[aria-selected="true"] p {
                color: #2c3e50 !important; /* Dark Blue-Grey instead of Red */
            }
            /* Selected Tab Top Border */
            div[data-testid="stTabs"] button[aria-selected="true"] {
                border-top-color: #2c3e50 !important;
            }
            div[data-testid="stTabs"] button:hover {
                color: #2c3e50 !important;
                border-color: #2c3e50 !important;
            }
        </style>
    """, unsafe_allow_html=True)

def inject_radio_tab_styles():
    """Injects CSS to style radio buttons as tabs."""
    st.markdown("""
    <style>
        /* Hide the default radio circles */
        div[data-testid="stRadio"] > label > div:first-child {
            display: none;
        }
        div[data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child {
            display: none;
        }
        
        /* Container styling */
        div[data-testid="stRadio"] > div[role="radiogroup"] {
            gap: 12px;
            border-bottom: 1px solid #ddd;
            padding-bottom: 0px;
        }

        /* Tab styling */
        div[data-testid="stRadio"] > div[role="radiogroup"] > label {
            background-color: transparent;
            padding: 8px 16px;
            border-radius: 8px 8px 0 0;
            border: 1px solid transparent; 
            margin-bottom: -1px;
            transition: all 0.2s;
        }
        
        /* Hover */
        div[data-testid="stRadio"] > div[role="radiogroup"] > label:hover {
            background-color: #f1f5f9;
            color: #0f172a;
        }
        
        /* Selected Tab Styling */
        div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) {
            background-color: #f1f5f9;
            border-bottom: 2px solid #2c3e50;
            color: #2c3e50;
        }
        
        div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) p {
            color: #2c3e50 !important;
            font-weight: 700;
        }
    </style>
    """, unsafe_allow_html=True)
