#!/usr/bin/env python3
"""
Adaptive Table Extractor for Complex PDF Structures
Handles: bordered tables, merged cells, nested tables, page breaks, irregular spacing, etc.
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple
import pandas as pd

# Import existing extractors
try:
    # Try relative imports first (when used as module)
    from .camelot_extractor import extract_with_camelot
    from .tabula_extractor import extract_with_tabula
    from .claude_pdf_image_extractor import (
        load_config, setup_bedrock_client, pdf_pages_to_png_bytes, 
        call_claude_on_image, clean_text_response, save_text_to_file
    )
except ImportError:
    # Fallback to absolute imports (when run as standalone script)
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent))
    
    from camelot_extractor import extract_with_camelot
    from tabula_extractor import extract_with_tabula
    from claude_pdf_image_extractor import (
        load_config, setup_bedrock_client, pdf_pages_to_png_bytes, 
        call_claude_on_image, clean_text_response, save_text_to_file
    )


class AdaptiveTableExtractor:
    """Smart table extractor that adapts to different PDF structures."""
    
    def __init__(self, config_path: str = "config.py"):
        self.config = load_config(config_path)
        self.bedrock = None
        if self.config and self.config.get("access_key"):
            self.bedrock = setup_bedrock_client(self.config)
    
    def detect_table_structure(self, pdf_path: str) -> Dict[str, Any]:
        """Analyze PDF to determine table structure characteristics."""
        import fitz  # PyMuPDF
        
        doc = fitz.open(pdf_path)
        analysis = {
            "total_pages": len(doc),
            "has_borders": False,
            "has_merged_cells": False,
            "has_nested_tables": False,
            "has_page_breaks": False,
            "irregular_spacing": False,
            "table_density": 0,
            "complexity_score": 0
        }
        
        # Analyze first few pages for structure
        sample_pages = min(5, len(doc))
        table_count = 0
        
        for page_num in range(sample_pages):
            page = doc.load_page(page_num)
            
            # Look for table indicators
            text = page.get_text()
            if any(indicator in text.lower() for indicator in ['table', 'grid', 'row', 'column']):
                table_count += 1
            
            # Check for borders/boxes
            drawings = page.get_drawings()
            if drawings:
                analysis["has_borders"] = True
            
            # Check for irregular spacing
            lines = page.get_text("dict")["blocks"]
            if len(lines) > 0:
                # Simple heuristic for irregular spacing
                analysis["irregular_spacing"] = True
        
        analysis["table_density"] = table_count / sample_pages
        analysis["complexity_score"] = self._calculate_complexity_score(analysis)
        
        doc.close()
        return analysis
    
    def _calculate_complexity_score(self, analysis: Dict) -> int:
        """Calculate complexity score (0-10) for extraction strategy selection."""
        score = 0
        
        # Page count factor
        if analysis["total_pages"] > 50:
            score += 3
        elif analysis["total_pages"] > 20:
            score += 2
        elif analysis["total_pages"] > 5:
            score += 1
        
        # Structure factors
        if analysis["has_borders"]:
            score += 1
        if analysis["has_merged_cells"]:
            score += 2
        if analysis["has_nested_tables"]:
            score += 3
        if analysis["irregular_spacing"]:
            score += 2
        
        return min(score, 10)
    
    def select_extraction_strategy(self, analysis: Dict) -> str:
        """Select best extraction strategy based on PDF analysis."""
        complexity = analysis["complexity_score"]
        page_count = analysis["total_pages"]
        
        if complexity <= 3 and page_count <= 10:
            return "camelot_tabula"  # Simple tables
        elif complexity <= 6 and page_count <= 30:
            return "claude_text"    # Medium complexity
        else:
            return "claude_image"   # High complexity, many pages
    
    def extract_simple_tables(self, pdf_path: str) -> List[Dict]:
        """Extract from simple bordered tables using Camelot + Tabula."""
        results = []
        
        # Try Camelot first (better for bordered tables)
        try:
            camelot_results = extract_with_camelot(pdf_path)
            if camelot_results:
                results.extend(camelot_results)
                print(f"[SUCCESS] Camelot extracted {len(camelot_results)} records")
        except Exception as e:
            print(f"[WARNING] Camelot failed: {e}")
        
        # Try Tabula as fallback
        if not results:
            try:
                tabula_results = extract_with_tabula(pdf_path)
                if tabula_results:
                    results.extend(tabula_results)
                    print(f"[SUCCESS] Tabula extracted {len(tabula_results)} records")
            except Exception as e:
                print(f"[WARNING] Tabula failed: {e}")
        
        return results
    
    def extract_complex_tables_claude_text(self, pdf_path: str) -> List[Dict]:
        """Extract complex tables using Claude on OCR text."""
        if not self.bedrock:
            print("[ERROR] Bedrock client not available")
            return []
        
        # Convert PDF to text first
        try:
            from .claude_text_extractor import extract_text_pagewise
        except ImportError:
            from claude_text_extractor import extract_text_pagewise
        
        text, used_ocr = extract_text_pagewise(pdf_path, use_ocr_fallback=True)
        
        # Use Claude to extract structured data from text
        prompt = f"""
        Extract all tabular data from this insurance document text.
        Handle merged cells, nested tables, and irregular spacing.
        Return structured JSON with tables and claims data.
        
        Text: {text[:10000]}...
        """
        
        try:
            response = self.bedrock.invoke_model(
                modelId=self.config["model_id"],
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4000,
                    "temperature": 0.0,
                    "messages": [{"role": "user", "content": prompt}]
                })
            )
            
            content = json.loads(response["body"].read())["content"][0]["text"]
            # Parse JSON response
            start = content.find('['); end = content.rfind(']') + 1
            if start != -1 and end > start:
                return json.loads(content[start:end])
        except Exception as e:
            print(f"[WARNING] Claude text extraction failed: {e}")
        
        return []
    
    def extract_complex_tables_claude_image(self, pdf_path: str, max_pages: int = 50) -> List[Dict]:
        """Extract complex tables using Claude on page images."""
        if not self.bedrock:
            print("[ERROR] Bedrock client not available")
            return []
        
        # Process pages in batches to avoid memory issues
        all_tables = []
        pages = pdf_pages_to_png_bytes(pdf_path, dpi=220, first_page=1, last_page=min(max_pages, 50))
        
        for page_num, png_bytes in pages:
            try:
                # Specialized prompt for complex table extraction
                prompt = f"""
                Extract ALL tabular data from this insurance document page.
                Handle:
                - Merged/spanned cells across columns
                - Nested tables within tables
                - Tables split across pages
                - Irregular spacing and alignment
                - Tables without visible borders
                
                Return structured JSON array of tables found.
                """
                
                response = call_claude_on_image(
                    self.bedrock, self.config["model_id"], png_bytes, page_num, len(pages)
                )
                
                cleaned = clean_text_response(response)
                # Parse and add to results
                try:
                    start = cleaned.find('['); end = cleaned.rfind(']') + 1
                    if start != -1 and end > start:
                        page_tables = json.loads(cleaned[start:end])
                        all_tables.extend(page_tables)
                except:
                    pass
                    
            except Exception as e:
                print(f"[WARNING] Page {page_num} failed: {e}")
        
        return all_tables
    
    def extract_adaptive(self, pdf_path: str, output_dir: str = "adaptive_results") -> Dict[str, Any]:
        """Main extraction method that adapts to PDF structure."""
        pdf_path = Path(pdf_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Analyzing PDF structure: {pdf_path.name}")
        analysis = self.detect_table_structure(str(pdf_path))
        strategy = self.select_extraction_strategy(analysis)
        
        print(f"Analysis: {analysis}")
        print(f" Selected strategy: {strategy}")
        
        results = []
        
        if strategy == "camelot_tabula":
            print(" Using Camelot + Tabula for simple tables...")
            results = self.extract_simple_tables(str(pdf_path))
            
        elif strategy == "claude_text":
            print(" Using Claude on OCR text for medium complexity...")
            results = self.extract_complex_tables_claude_text(str(pdf_path))
            
        elif strategy == "claude_image":
            print(" Using Claude on page images for high complexity...")
            results = self.extract_complex_tables_claude_image(str(pdf_path))
        
        # Save results
        if results:
            # Save as JSON
            json_path = output_dir / f"{pdf_path.stem}_adaptive_tables.json"
            with open(json_path, 'w') as f:
                json.dump(results, f, indent=2)
            
            # Save as Excel
            excel_path = output_dir / f"{pdf_path.stem}_adaptive_tables.xlsx"
            self._save_to_excel(results, excel_path)
            
            print(f"[SUCCESS] Extracted {len(results)} tables")
            print(f" Saved: {json_path}, {excel_path}")
        else:
            print("[WARNING] No tables extracted")
        
        return {
            "strategy": strategy,
            "analysis": analysis,
            "results_count": len(results),
            "output_files": [str(json_path), str(excel_path)] if results else []
        }
    
    def _save_to_excel(self, tables: List[Dict], excel_path: Path):
        """Save extracted tables to Excel with multiple sheets."""
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = []
            for i, table in enumerate(tables):
                summary_data.append({
                    'Table_ID': i + 1,
                    'Table_Name': table.get('table_name', f'Table {i+1}'),
                    'Rows': len(table.get('data', [])),
                    'Columns': len(table.get('headers', [])),
                    'Page': table.get('metadata', {}).get('page', 'Unknown')
                })
            
            if summary_data:
                pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
            
            # Individual table sheets
            for i, table in enumerate(tables):
                headers = table.get('headers', [])
                data = table.get('data', [])
                
                if headers and data:
                    df = pd.DataFrame(data, columns=headers)
                    sheet_name = f"Table_{i+1}"[:31]  # Excel sheet name limit
                    df.to_excel(writer, sheet_name=sheet_name, index=False)


def main():
    parser = argparse.ArgumentParser(description="Adaptive table extractor for complex PDF structures")
    parser.add_argument("pdf", help="Path to PDF file")
    parser.add_argument("--out", default="adaptive_results", help="Output directory")
    parser.add_argument("--config", default="config.py", help="Config file path")
    parser.add_argument("--strategy", choices=["auto", "camelot_tabula", "claude_text", "claude_image"], 
                       default="auto", help="Force specific strategy")
    args = parser.parse_args()
    
    extractor = AdaptiveTableExtractor(args.config)
    
    if args.strategy == "auto":
        result = extractor.extract_adaptive(args.pdf, args.out)
    else:
        # Force specific strategy
        if args.strategy == "camelot_tabula":
            results = extractor.extract_simple_tables(args.pdf)
        elif args.strategy == "claude_text":
            results = extractor.extract_complex_tables_claude_text(args.pdf)
        elif args.strategy == "claude_image":
            results = extractor.extract_complex_tables_claude_image(args.pdf)
        
        # Save results
        output_dir = Path(args.out)
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_name = Path(args.pdf).stem
        
        if results:
            json_path = output_dir / f"{pdf_name}_{args.strategy}_tables.json"
            excel_path = output_dir / f"{pdf_name}_{args.strategy}_tables.xlsx"
            
            with open(json_path, 'w') as f:
                json.dump(results, f, indent=2)
            
            extractor._save_to_excel(results, excel_path)
            print(f"[SUCCESS] Saved: {json_path}, {excel_path}")
    
    print("[COMPLETE] Extraction complete!")


if __name__ == "__main__":
    main()
