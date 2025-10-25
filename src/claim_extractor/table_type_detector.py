#!/usr/bin/env python3
"""
Table Type Detector for PDF Analysis
Detects different table structures and recommends extraction strategies.
"""

import fitz  # PyMuPDF
from pathlib import Path
from typing import Dict, List, Any
import re


class TableTypeDetector:
    """Detects table types and complexity in PDFs."""
    
    def __init__(self):
        self.table_indicators = [
            'claim number', 'claim no', 'loss date', 'paid loss', 'reserve',
            'alae', 'bodily injury', 'property damage', 'indemnity', 'medical',
            'evaluation date', 'carrier', 'company', 'insurer'
        ]
    
    def analyze_pdf_structure(self, pdf_path: str) -> Dict[str, Any]:
        """Comprehensive PDF structure analysis."""
        doc = fitz.open(pdf_path)
        analysis = {
            "total_pages": len(doc),
            "table_types": [],
            "complexity_indicators": {},
            "recommended_strategy": "unknown",
            "confidence_score": 0
        }
        
        # Analyze first 10 pages for structure
        sample_pages = min(10, len(doc))
        page_analyses = []
        
        for page_num in range(sample_pages):
            page_analysis = self._analyze_page(doc.load_page(page_num), page_num)
            page_analyses.append(page_analysis)
        
        # Aggregate analysis
        analysis.update(self._aggregate_analysis(page_analyses))
        analysis["recommended_strategy"] = self._recommend_strategy(analysis)
        
        doc.close()
        return analysis
    
    def _analyze_page(self, page, page_num: int) -> Dict[str, Any]:
        """Analyze a single page for table characteristics."""
        analysis = {
            "page": page_num,
            "has_borders": False,
            "has_merged_cells": False,
            "has_nested_structure": False,
            "table_density": 0,
            "text_blocks": 0,
            "drawings": 0,
            "table_indicators": 0
        }
        
        # Get page content
        text = page.get_text()
        text_dict = page.get_text("dict")
        drawings = page.get_drawings()
        
        # Count text blocks
        blocks = text_dict.get("blocks", [])
        analysis["text_blocks"] = len([b for b in blocks if b.get("type") == 0])
        analysis["drawings"] = len(drawings)
        
        # Check for borders (drawings/rectangles)
        if drawings:
            analysis["has_borders"] = True
        
        # Look for table indicators in text
        text_lower = text.lower()
        indicator_count = sum(1 for indicator in self.table_indicators if indicator in text_lower)
        analysis["table_indicators"] = indicator_count
        
        # Calculate table density
        if analysis["text_blocks"] > 0:
            analysis["table_density"] = indicator_count / analysis["text_blocks"]
        
        # Check for merged cell patterns (multiple spaces, alignment)
        if self._detect_merged_cells(text):
            analysis["has_merged_cells"] = True
        
        # Check for nested structure (indented text, sub-tables)
        if self._detect_nested_structure(text):
            analysis["has_nested_structure"] = True
        
        return analysis
    
    def _detect_merged_cells(self, text: str) -> bool:
        """Detect potential merged cells based on text patterns."""
        # Look for irregular spacing patterns
        lines = text.split('\n')
        for line in lines:
            # Multiple consecutive spaces might indicate merged cells
            if re.search(r'\s{3,}', line):
                return True
            # Tab-separated values with irregular spacing
            if '\t' in line and len(line.split('\t')) > 3:
                return True
        return False
    
    def _detect_nested_structure(self, text: str) -> bool:
        """Detect nested table structures."""
        lines = text.split('\n')
        indent_levels = []
        
        for line in lines:
            if line.strip():
                indent = len(line) - len(line.lstrip())
                indent_levels.append(indent)
        
        # If we have multiple indent levels, might be nested
        if len(set(indent_levels)) > 2:
            return True
        
        # Look for sub-table indicators
        sub_indicators = ['subtotal', 'total', 'summary', 'breakdown', 'detail']
        text_lower = text.lower()
        if any(indicator in text_lower for indicator in sub_indicators):
            return True
        
        return False
    
    def _aggregate_analysis(self, page_analyses: List[Dict]) -> Dict[str, Any]:
        """Aggregate page analyses into overall structure assessment."""
        total_pages = len(page_analyses)
        
        # Calculate averages and totals
        avg_table_density = sum(p["table_density"] for p in page_analyses) / total_pages
        total_indicators = sum(p["table_indicators"] for p in page_analyses)
        pages_with_borders = sum(1 for p in page_analyses if p["has_borders"])
        pages_with_merged = sum(1 for p in page_analyses if p["has_merged_cells"])
        pages_with_nested = sum(1 for p in page_analyses if p["has_nested_structure"])
        
        # Determine table types
        table_types = []
        if pages_with_borders > total_pages * 0.3:
            table_types.append("bordered_tables")
        if pages_with_merged > total_pages * 0.2:
            table_types.append("merged_cells")
        if pages_with_nested > total_pages * 0.2:
            table_types.append("nested_tables")
        if avg_table_density > 0.5:
            table_types.append("high_density")
        
        # Calculate complexity score
        complexity_score = 0
        if total_pages > 50:
            complexity_score += 3
        elif total_pages > 20:
            complexity_score += 2
        elif total_pages > 5:
            complexity_score += 1
        
        if pages_with_merged > total_pages * 0.3:
            complexity_score += 2
        if pages_with_nested > total_pages * 0.3:
            complexity_score += 2
        if avg_table_density > 0.7:
            complexity_score += 1
        
        return {
            "table_types": table_types,
            "complexity_indicators": {
                "avg_table_density": avg_table_density,
                "total_indicators": total_indicators,
                "pages_with_borders": pages_with_borders,
                "pages_with_merged_cells": pages_with_merged,
                "pages_with_nested_structure": pages_with_nested,
                "complexity_score": complexity_score
            },
            "confidence_score": min(100, (total_indicators / total_pages) * 20)
        }
    
    def _recommend_strategy(self, analysis: Dict) -> str:
        """Recommend extraction strategy based on analysis."""
        complexity = analysis["complexity_indicators"]["complexity_score"]
        page_count = analysis["total_pages"]
        table_types = analysis["table_types"]
        
        # Simple strategy for basic tables
        if complexity <= 2 and page_count <= 10 and "bordered_tables" in table_types:
            return "camelot_tabula"
        
        # Medium complexity - use Claude on text
        elif complexity <= 5 and page_count <= 30:
            return "claude_text"
        
        # High complexity - use Claude on images
        elif complexity > 5 or page_count > 30 or "merged_cells" in table_types or "nested_tables" in table_types:
            return "claude_image"
        
        # Default to text-based extraction
        else:
            return "claude_text"
    
    def get_extraction_plan(self, pdf_path: str) -> Dict[str, Any]:
        """Get detailed extraction plan for a PDF."""
        analysis = self.analyze_pdf_structure(pdf_path)
        
        plan = {
            "pdf_path": pdf_path,
            "analysis": analysis,
            "recommended_strategy": analysis["recommended_strategy"],
            "alternative_strategies": self._get_alternative_strategies(analysis),
            "estimated_time": self._estimate_processing_time(analysis),
            "success_probability": self._calculate_success_probability(analysis)
        }
        
        return plan
    
    def _get_alternative_strategies(self, analysis: Dict) -> List[str]:
        """Get alternative strategies if primary fails."""
        primary = analysis["recommended_strategy"]
        alternatives = []
        
        if primary == "camelot_tabula":
            alternatives = ["claude_text", "claude_image"]
        elif primary == "claude_text":
            alternatives = ["claude_image", "camelot_tabula"]
        elif primary == "claude_image":
            alternatives = ["claude_text", "camelot_tabula"]
        
        return alternatives
    
    def _estimate_processing_time(self, analysis: Dict) -> str:
        """Estimate processing time based on complexity."""
        pages = analysis["total_pages"]
        complexity = analysis["complexity_indicators"]["complexity_score"]
        strategy = analysis["recommended_strategy"]
        
        if strategy == "camelot_tabula":
            return f"{pages * 2}-{pages * 5} seconds"
        elif strategy == "claude_text":
            return f"{pages * 10}-{pages * 30} seconds"
        elif strategy == "claude_image":
            return f"{pages * 15}-{pages * 45} seconds"
        
        return "Unknown"
    
    def _calculate_success_probability(self, analysis: Dict) -> int:
        """Calculate success probability percentage."""
        confidence = analysis["confidence_score"]
        complexity = analysis["complexity_indicators"]["complexity_score"]
        
        # Base probability from confidence
        base_prob = min(95, confidence)
        
        # Adjust for complexity
        if complexity <= 3:
            return min(95, base_prob + 10)
        elif complexity <= 6:
            return max(60, base_prob - 10)
        else:
            return max(40, base_prob - 20)


def main():
    """Test the table type detector."""
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python table_type_detector.py <pdf_path>")
        return
    
    pdf_path = sys.argv[1]
    detector = TableTypeDetector()
    
    print(f"🔍 Analyzing PDF: {pdf_path}")
    plan = detector.get_extraction_plan(pdf_path)
    
    print(f"\n📊 Analysis Results:")
    print(f"  Pages: {plan['analysis']['total_pages']}")
    print(f"  Table Types: {', '.join(plan['analysis']['table_types'])}")
    print(f"  Complexity Score: {plan['analysis']['complexity_indicators']['complexity_score']}")
    print(f"  Confidence: {plan['analysis']['confidence_score']}%")
    
    print(f"\n🎯 Recommended Strategy: {plan['recommended_strategy']}")
    print(f"  Success Probability: {plan['success_probability']}%")
    print(f"  Estimated Time: {plan['estimated_time']}")
    
    print(f"\n🔄 Alternative Strategies: {', '.join(plan['alternative_strategies'])}")


if __name__ == "__main__":
    main()
