import io

import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
import pandas as pd
import streamlit as st
from mlxtend.frequent_patterns import apriori, association_rules


st.set_page_config(
    page_title="Smart Retail Analytics",
    page_icon="🛒",
    layout="wide",
)


THEME_CSS = """
<style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1280px;
    }

.hero {
    padding: 2rem;
    border-left: 6px solid #2e7d32;
    background: #f7faf7;
    border-radius: 12px;
    margin-bottom: 1.5rem;
    text-align: center;
}

.hero h1 {
    margin: 0 0 .7rem 0;
    font-size: 3rem;
    color: #1f3d2b;
    font-weight: 700;
}

.hero p {
    margin: auto;
    color: #4d5c52;
    font-size: 1.1rem;
    line-height: 1.7;
    max-width: 1000px;
}

    .section-note {
        color: #5d665f;
        font-size: .95rem;
        margin-top: -.4rem;
        margin-bottom: .9rem;
    }

    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e6ebe7;
        padding: 1rem;
        border-radius: 8px;
    }

    div[data-testid="stSidebar"] {
        background: #f5f7f5;
    }
</style>
"""


st.markdown(THEME_CSS, unsafe_allow_html=True)


def render_header():
    st.markdown(
        """
        <div class="hero">
            <h1>Smart Retail Analytics Dashboard</h1>
            <p>    
                Discover product relationships, customer buying patterns,
                and cross-selling opportunities using Market Basket Analysis
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
def render_sidebar():
    st.sidebar.title("Dashboard")
    st.sidebar.write(
        "Use this tool to clean retail transactions, find frequent itemsets, "
        "and generate product recommendation rules."
    )

    st.sidebar.markdown("### What this dashboard does")
    st.sidebar.markdown(
        """
        - Cleans transaction records
        - Builds a basket matrix
        - Finds frequent product combinations
        - Generates association rules
        - Highlights useful cross-sell ideas
        - Exports the final rules as CSV
        """
    )

    st.sidebar.info("Best suited for retail, grocery, supermarket, bakery, or e-commerce order data.")


def render_dataset_help():
    with st.expander("Dataset requirements", expanded=False):
        st.markdown(
            """
            This dashboard expects transaction-level retail data. Each row should represent
            one product inside one order, bill, basket, or customer session.

            Required columns:

            | Column type | Example names | Purpose |
            | --- | --- | --- |
            | Transaction ID | `InvoiceNo`, `Order_ID`, `Transaction`, `Session_ID` | Groups products into one basket |
            | Product | `Description`, `Product_Name`, `Item`, `SKU` | Identifies the product bought |

            Optional column:

            | Column type | Example names | Purpose |
            | --- | --- | --- |
            | Quantity | `Quantity`, `Qty`, `Units` | Removes returns and helps count basket contents |

            Example:

            | Order_ID | Product_Name | Quantity |
            | --- | --- | --- |
            | ORD1001 | Coffee | 2 |
            | ORD1001 | Cake | 1 |
            | ORD1002 | Bread | 3 |
            | ORD1002 | Butter | 1 |

            Datasets that are not transactional, such as student marks, weather records,
            movies, images, or category-only tables, will not produce meaningful rules.
            """
        )


@st.cache_data(show_spinner=False)
def load_data(file_bytes):
    return pd.read_csv(io.BytesIO(file_bytes), encoding="latin1")


def clean_data(df, transaction_col, product_col, quantity_col=None):
    cleaned = df.copy()

    cleaned[transaction_col] = cleaned[transaction_col].astype(str).str.strip()
    cleaned[product_col] = cleaned[product_col].astype(str).str.strip()

    cleaned = cleaned.dropna(subset=[transaction_col, product_col])
    cleaned = cleaned[(cleaned[transaction_col] != "") & (cleaned[product_col] != "")]

    # Many retail datasets mark cancelled invoices with a leading C.
    cleaned = cleaned[~cleaned[transaction_col].str.upper().str.startswith("C")]

    if quantity_col:
        cleaned[quantity_col] = pd.to_numeric(cleaned[quantity_col], errors="coerce")
        cleaned = cleaned[cleaned[quantity_col] > 0]

    return cleaned.drop_duplicates()


def create_basket(df, transaction_col, product_col, quantity_col=None):
    if quantity_col:
        basket = (
            df.groupby([transaction_col, product_col])[quantity_col]
            .sum()
            .unstack(fill_value=0)
        )
    else:
        basket = (
            df.groupby([transaction_col, product_col])
            .size()
            .unstack(fill_value=0)
        )

    return basket.gt(0).astype(bool)


def build_rules(basket, min_support, min_confidence):
    frequent_itemsets = apriori(
        basket,
        min_support=min_support,
        use_colnames=True,
        low_memory=True,
    )

    if frequent_itemsets.empty:
        return frequent_itemsets, pd.DataFrame()

    rules = association_rules(
        frequent_itemsets,
        metric="confidence",
        min_threshold=min_confidence,
    )

    if rules.empty:
        return frequent_itemsets, rules

    rules = rules[(rules["lift"] > 1) & (rules["confidence"] >= min_confidence)].copy()
    rules["Rule Strength"] = rules["lift"].apply(classify_rule_strength)
    rules["Recommendation"] = rules.apply(format_recommendation, axis=1)

    return frequent_itemsets, rules.sort_values(["lift", "confidence"], ascending=False)


def classify_rule_strength(lift):
    if lift >= 10:
        return "Very strong"
    if lift >= 5:
        return "Strong"
    if lift >= 2:
        return "Moderate"
    return "Weak"


def format_itemset(itemset):
    return ", ".join(sorted(str(item) for item in itemset))


def format_recommendation(row):
    antecedents = format_itemset(row["antecedents"])
    consequents = format_itemset(row["consequents"])
    return f"If a customer buys {antecedents}, recommend {consequents}."


def show_data_quality(df):
    st.subheader("Dataset overview")
    st.markdown(
        "<p class='section-note'>A quick check before running the analysis.</p>",
        unsafe_allow_html=True,
    )

    metric_a, metric_b, metric_c, metric_d = st.columns(4)
    metric_a.metric("Rows", f"{len(df):,}")
    metric_b.metric("Columns", f"{len(df.columns):,}")
    metric_c.metric("Missing values", f"{int(df.isna().sum().sum()):,}")
    metric_d.metric("Duplicate rows", f"{int(df.duplicated().sum()):,}")

    st.dataframe(df.head(20), use_container_width=True)


def show_cleaned_metrics(cleaned_df, transaction_col, product_col):
    metric_a, metric_b, metric_c = st.columns(3)
    metric_a.metric("Transactions", f"{cleaned_df[transaction_col].nunique():,}")
    metric_b.metric("Unique products", f"{cleaned_df[product_col].nunique():,}")
    metric_c.metric("Clean records", f"{len(cleaned_df):,}")


def plot_top_products(cleaned_df, product_col):

    top_products = (
        cleaned_df[product_col]
        .value_counts()
        .head(15)
        .sort_values()
    )

    fig = px.bar(
        x=top_products.values,
        y=top_products.index,
        orientation='h',
        color=top_products.values,
        color_continuous_scale='Viridis',
        text=top_products.values,
        labels={
            "x": "Purchase Count",
            "y": ""
        },
        title="Top Purchased Products"
    )

    fig.update_layout(
        template="plotly_white",
        height=550,
        title_font_size=24,
        coloraxis_showscale=False
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

def plot_top_rules(rules):

    top_rules = rules.head(10).copy()

    top_rules["Label"] = (
        top_rules["antecedents"]
        .apply(format_itemset)
    )

    fig = px.bar(
        top_rules,
        x="lift",
        y="Label",
        orientation="h",
        color="confidence",
        color_continuous_scale="Plasma",
        text="lift",
        title="Strong Product Associations"
    )

    fig.update_layout(
        template="plotly_white",
        height=550,
        title_font_size=24
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )
def plot_rule_strength_distribution(rules):

    strength_counts = (
        rules["Rule Strength"]
        .value_counts()
        .reset_index()
    )

    strength_counts.columns = [
        "Strength",
        "Count"
    ]

    fig = px.pie(
        strength_counts,
        names="Strength",
        values="Count",
        title="Rule Strength Distribution",
        hole=0.45,
        color_discrete_sequence=px.colors.qualitative.Set2
    )

    fig.update_layout(
        height=500
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


def plot_support_confidence(rules):

    fig = px.scatter(
        rules.head(100),
        x="support",
        y="confidence",
        size="lift",
        color="lift",
        hover_data=["Rule Strength"],
        title="Support vs Confidence Analysis",
        color_continuous_scale="Turbo"
    )

    fig.update_layout(
        template="plotly_white",
        height=550
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

def prepare_rule_table(rules):
    display_rules = rules.copy()
    display_rules["Antecedents"] = display_rules["antecedents"].apply(format_itemset)
    display_rules["Consequents"] = display_rules["consequents"].apply(format_itemset)

    return display_rules[
        [
            "Antecedents",
            "Consequents",
            "support",
            "confidence",
            "lift",
            "Rule Strength",
            "Recommendation",
        ]
    ].rename(
        columns={
            "support": "Support",
            "confidence": "Confidence",
            "lift": "Lift",
        }
    )


def run_analysis(df, transaction_col, product_col, quantity_col, min_support, min_confidence, product_limit):
    if transaction_col == product_col:
        st.error("Choose different columns for transaction ID and product.")
        return

    with st.spinner("Cleaning transaction records..."):
        cleaned_df = clean_data(df, transaction_col, product_col, quantity_col)

    if cleaned_df.empty:
        st.error("No usable records were found after cleaning. Check the selected columns.")
        return

    st.success("Dataset cleaned successfully.")
    show_cleaned_metrics(cleaned_df, transaction_col, product_col)

    with st.expander("Preview cleaned data", expanded=False):
        st.dataframe(cleaned_df.head(25), use_container_width=True)

    top_product_names = cleaned_df[product_col].value_counts().head(product_limit).index
    model_df = cleaned_df[cleaned_df[product_col].isin(top_product_names)]

    with st.spinner("Creating basket matrix..."):
        basket = create_basket(model_df, transaction_col, product_col, quantity_col)

    if basket.shape[0] < 2 or basket.shape[1] < 2:
        st.error("The selected data does not contain enough transactions or products for basket analysis.")
        return

    with st.spinner("Finding frequent itemsets and association rules..."):
        frequent_itemsets, rules = build_rules(basket, min_support, min_confidence)

    if frequent_itemsets.empty:
        st.warning("No frequent itemsets were found. Lower the support value and try again.")
        return

    tabs = st.tabs(["Rules", "Visuals", "Recommendations", "Export"])

    with tabs[0]:
        st.subheader("Frequent itemsets")
        itemset_preview = frequent_itemsets.sort_values("support", ascending=False).head(20).copy()
        itemset_preview["itemsets"] = itemset_preview["itemsets"].apply(format_itemset)
        st.dataframe(itemset_preview, use_container_width=True)

        st.subheader("Association rules")
        if rules.empty:
            st.warning("Frequent itemsets were found, but no strong rules matched the confidence setting.")
        else:
            st.dataframe(prepare_rule_table(rules).head(25), use_container_width=True)

    with tabs[1]:
               visual_a, visual_b = st.columns(2)
               with visual_a:
                   plot_top_products(
                model_df,
                product_col
            )
               with visual_b:
                    if rules.empty:
                        st.info(
                    "No rule chart available."
                )
                    else:
                           plot_top_rules(rules)


    with tabs[2]:
        st.subheader("Business recommendations")
        if rules.empty:
            st.info("Try reducing minimum confidence to discover more recommendation rules.")
        else:
            for _, row in rules.head(8).iterrows():
                st.write(f"- {row['Recommendation']} Lift: {row['lift']:.2f}, confidence: {row['confidence']:.2%}.")

            st.markdown("### Practical actions")
            st.write("- Place high-lift product pairs near each other in-store or on product pages.")
            st.write("- Use moderate and strong rules for bundle offers, checkout suggestions, and email campaigns.")
            st.write("- Review popular products separately for inventory planning and replenishment.")

    with tabs[3]:
        if rules.empty:
            st.info("There are no rules to export yet.")
        else:
            export_table = prepare_rule_table(rules)
            st.download_button(
                label="Download association rules",
                data=export_table.to_csv(index=False),
                file_name="retail_association_rules.csv",
                mime="text/csv",
            )


render_header()
render_sidebar()
render_dataset_help()

uploaded_file = st.file_uploader("Upload Retail Transaction Dataset (CSV)", type=["csv"])

if uploaded_file is None:
    st.info("Upload a CSV file to begin.")
    st.stop()

try:
    df = load_data(uploaded_file.getvalue())
except Exception as exc:
    st.error(f"Could not read the uploaded file: {exc}")
    st.stop()

show_data_quality(df)

st.subheader("Configure analysis")
st.markdown(
    "<p class='section-note'>Select the columns that identify baskets and products.</p>",
    unsafe_allow_html=True,
)

columns = df.columns.tolist()
config_a, config_b = st.columns(2)

with config_a:
    transaction_col = st.selectbox("Transaction column", columns)
    product_col = st.selectbox("Product column", columns, index=min(1, len(columns) - 1))

with config_b:
    quantity_enabled = st.checkbox("This dataset has a quantity column")
    quantity_col = st.selectbox("Quantity column", columns) if quantity_enabled else None

setting_a, setting_b, setting_c = st.columns(3)

with setting_a:
    min_support = st.slider(
        "Minimum support",
        min_value=0.01,
        max_value=0.50,
        value=0.05,
        step=0.01,
    )

with setting_b:
    min_confidence = st.slider(
        "Minimum confidence",
        min_value=0.10,
        max_value=1.00,
        value=0.30,
        step=0.05,
    )

with setting_c:
    product_limit = st.slider(
        "Top products to include",
        min_value=20,
        max_value=200,
        value=100,
        step=10,
        help="Keeping the most common products makes large datasets faster to analyze.",
    )

with st.expander(
    "ℹ Understanding Support, Confidence & Product Limit"
):

    st.markdown("""

### 📌 Minimum Support
Support shows how often a product combination appears in transactions.

- Lower support → Finds more product combinations
- Higher support → Shows only the most common combinations

#### Recommended Values
| Dataset Size | Recommended Support |
|---|---|
| Small Dataset | 0.01 - 0.05 |
| Medium Dataset | 0.05 - 0.10 |
| Large Dataset | 0.10 - 0.20 |

---

### 📌 Minimum Confidence
Confidence shows how reliable a recommendation rule is.

Example:
If customers buy Bread, how often do they also buy Butter?

- Lower confidence → More recommendations
- Higher confidence → Stronger and more reliable recommendations

#### Recommended Values
| Use Case | Recommended Confidence |
|---|---|
| Basic Exploration | 0.10 - 0.30 |
| Strong Recommendations | 0.30 - 0.60 |
| Very Strict Rules | 0.60+ |

---

### 📌 Top Products to Include
This controls how many of the most purchased products are included in the analysis.

- Lower value → Faster analysis
- Higher value → More detailed analysis but slower performance

#### Example
If set to:
- 50 → Only top 50 most purchased products are analyzed
- 100 → Top 100 products are analyzed

This helps improve performance on large retail datasets.

    """)

if st.button("Run Retail Analysis", type="primary"):
    run_analysis(
        df=df,
        transaction_col=transaction_col,
        product_col=product_col,
        quantity_col=quantity_col,
        min_support=min_support,
        min_confidence=min_confidence,
        product_limit=product_limit,
    )

st.divider()
st.caption("Built with Streamlit, pandas, matplotlib, and the Apriori algorithm.")
