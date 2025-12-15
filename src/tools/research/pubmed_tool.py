import os
import requests
import xml.etree.ElementTree as ET
from typing import Dict, List

def pubmed_agent(state: Dict) -> Dict:
    """
    Searches PubMed for medical research papers using NCBI E-utilities.
    """
    query = state.get("query", "")
    print(f"🔬 [PubMed] Searching for: {query}")

    api_key = os.getenv("PUBMED_API_KEY")
    
    # 1. Search for IDs
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    search_params = {
        "db": "pubmed",
        "term": query,
        "retmax": 5,
        "retmode": "json"
    }
    if api_key:
        search_params["api_key"] = api_key

    try:
        response = requests.get(search_url, params=search_params, timeout=10)
        response.raise_for_status()
        search_data = response.json()
        
        id_list = search_data.get("esearchresult", {}).get("idlist", [])
        
        if not id_list:
            print("⚠️ [PubMed] No papers found")
            return {
                **state,
                "results": [f"No PubMed papers found for '{query}'."]
            }

        # 2. Fetch details for these IDs
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml"
        }
        if api_key:
            fetch_params["api_key"] = api_key

        fetch_response = requests.get(fetch_url, params=fetch_params, timeout=10)
        fetch_response.raise_for_status()
        
        # Parse XML
        root = ET.fromstring(fetch_response.content)
        formatted_results = []
        
        for article in root.findall(".//PubmedArticle"):
            title = article.findtext(".//ArticleTitle", "No Title")
            
            # Extract Abstract (can be multiple parts)
            abstract_list = article.findall(".//AbstractText")
            abstract = " ".join([elem.text for elem in abstract_list if elem.text])
            if not abstract:
                abstract = "No abstract available."
            
            # Truncate abstract
            if len(abstract) > 400:
                abstract = abstract[:400] + "..."

            # Extract Journal and Year
            journal = article.findtext(".//Journal/Title", "Unknown Journal")
            year = article.findtext(".//PubDate/Year", "Unknown Year")
            
            # Extract PMID
            pmid = article.findtext(".//PMID", "")
            
            link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

            result_str = f"""**{title}**
Source: PubMed ({journal}, {year})
Link: {link}

Abstract: {abstract}
"""
            formatted_results.append(result_str)

        print(f"✅ [PubMed] Found {len(formatted_results)} papers")
        
        return {
            **state,
            "results": formatted_results
        }

    except Exception as e:
        print(f"❌ [PubMed] Error: {e}")
        return {
            **state,
            "results": [f"Error searching PubMed: {str(e)}"]
        }

if __name__ == "__main__":
    # Simple test
    test_state = {"query": "covid-19 vaccine side effects"}
    res = pubmed_agent(test_state)
    print("\n".join(res["results"]))
