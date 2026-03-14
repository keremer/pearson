# pearson/interop/google_docs/parser.py (updated with improvements)
"""
Google Docs Document Parser - Structured content extraction with improved parsing.
"""
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from .. import BaseContentParser


class GoogleDocsParser(BaseContentParser):
    """Enhanced Google Docs parser with Bloom's taxonomy and assessment classification."""
    
    def __init__(self):
        self.section_handlers = {
            'learning outcomes': self._parse_learning_outcomes,
            'assessment': self._parse_assessments,
            'tools': self._parse_tools,
            'weekly structure': self._parse_weekly_schedule,
            'course description': self._parse_course_description,
            'objectives': self._parse_learning_outcomes,  # Alias
            'learning objectives': self._parse_learning_outcomes,  # Alias
        }
    
    def parse_to_course_structure(self, external_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Google Doc into our course data structure.
        
        Args:
            external_content: Content from GoogleDocsClient.get_content()
                
        Returns:
            Dictionary with structured course data
        """
        if not external_content:
            return {
                'title': 'Untitled',
                'source_platform': 'google_docs',
                'learning_outcomes': [],
                'assessment_formats': [],
                'tools': [],
                'lessons': [],
                'metadata': {
                    'parsed_at': datetime.now().isoformat(),
                    'error': 'No content provided'
                }
            }
        
        # Extract raw document and metadata based on format
        raw_document, title, document_id, modified_time = self._extract_content_and_metadata(external_content)
        
        if not raw_document:
            return {
                'title': title or 'Untitled',
                'source_platform': 'google_docs',
                'learning_outcomes': [],
                'assessment_formats': [],
                'tools': [],
                'lessons': [],
                'metadata': {
                    'document_id': document_id,
                    'last_modified': modified_time,
                    'parsed_at': datetime.now().isoformat(),
                    'error': 'Could not extract document content'
                }
            }
        
        # Parse the document structure
        structured_data = self._parse_document_structure(raw_document, title, document_id, modified_time)
        
        # Map to course model
        course_data = self._map_to_course_model(structured_data)
        
        # Add parsing metadata
        course_data['metadata']['parsed_at'] = datetime.now().isoformat()
        course_data['metadata']['parser_version'] = '2.0'
        course_data['metadata']['content_format'] = self._detect_content_format(external_content)
        
        return course_data
    
    def parse_from_course_structure(self, course_data: Dict[str, Any], 
                                   format: Optional[str] = None) -> str:
        """
        Parse course structure to Google Docs format.
        
        Args:
            course_data: Course structure dictionary
            format: Output format (optional)
            
        Returns:
            Formatted content for Google Docs
        """
        # This method should convert our course structure back to a format
        # suitable for Google Docs. For now, we'll create a simple text representation.
        sections = []
        
        # Add title
        title = course_data.get('title', 'Untitled Course')
        sections.append(f"# {title}")
        sections.append("")
        
        # Add description
        if course_data.get('course_description'):
            sections.append("## Course Description")
            sections.append(course_data['course_description'])
            sections.append("")
        
        # Add learning outcomes
        if course_data.get('learning_outcomes'):
            sections.append("## Learning Outcomes")
            for outcome in course_data['learning_outcomes']:
                code = outcome.get('code', '')
                description = outcome.get('description', '')
                sections.append(f"- **{code}:** {description}")
            sections.append("")
        
        # Add assessment formats
        if course_data.get('assessment_formats'):
            sections.append("## Assessment")
            for assessment in course_data['assessment_formats']:
                sections.append(f"- **{assessment.get('type', 'Assessment')}:** {assessment.get('description', '')}")
            sections.append("")
        
        # Add tools
        if course_data.get('tools'):
            sections.append("## Tools & Resources")
            for tool in course_data['tools']:
                sections.append(f"- **{tool.get('name', 'Tool')}:** {tool.get('description', '')}")
            sections.append("")
        
        # Add lessons/schedule
        if course_data.get('lessons'):
            sections.append("## Course Schedule")
            for lesson in course_data['lessons']:
                week = lesson.get('week', lesson.get('order', '?'))
                topic = lesson.get('topic', lesson.get('title', 'Untitled'))
                sections.append(f"### Week {week}: {topic}")
                if lesson.get('content'):
                    sections.append(lesson['content'])
                sections.append("")
        
        return '\n'.join(sections)
    
    def _extract_content_and_metadata(self, external_content: Dict[str, Any]) -> tuple:
        """
        Extract raw document and metadata from various input formats.
        
        Returns:
            Tuple of (raw_document, title, document_id, modified_time)
        """
        raw_document = None
        title = None
        document_id = None
        modified_time = None
        
        # Format 1: Client's new format (with 'content' and 'raw' keys)
        if 'content' in external_content and 'raw' in external_content['content']:
            raw_document = external_content['content']['raw']
            title = external_content.get('title', '')
            document_id = external_content.get('id')
            
            # Get metadata from client format
            metadata = external_content.get('metadata', {})
            modified_time = metadata.get('modified_time')
            
            # If no title in main object, try raw document
            if not title and raw_document:
                title = raw_document.get('title', 'Untitled')
        
        # Format 2: Raw Google Docs API response (old format)
        elif 'body' in external_content and 'content' in external_content['body']:
            raw_document = external_content
            title = external_content.get('title', 'Untitled')
            document_id = external_content.get('documentId')
            
            # Get metadata from raw document
            if '_metadata' in external_content:
                metadata = external_content['_metadata']
                modified_time = metadata.get('modified_time')
            else:
                # Try to get modified time from document structure
                modified_time = external_content.get('modifiedTime')
        
        # Format 3: Minimal format with just raw document
        elif isinstance(external_content, dict) and any(key in external_content for key in ['title', 'body']):
            raw_document = external_content
            title = external_content.get('title', 'Untitled')
            document_id = external_content.get('documentId') or external_content.get('id')
            modified_time = external_content.get('modifiedTime')
        
        return raw_document, title, document_id, modified_time
    
    def _detect_content_format(self, external_content: Dict[str, Any]) -> str:
        """Detect the format of the input content."""
        if 'content' in external_content and 'raw' in external_content['content']:
            return 'client_enriched'
        elif 'body' in external_content and 'content' in external_content['body']:
            return 'raw_google_docs'
        elif '_metadata' in external_content:
            return 'raw_with_metadata'
        else:
            return 'unknown'
    
    def _parse_document_structure(self, raw_document: Dict[str, Any], 
                                title: str, document_id: Optional[str], 
                                modified_time: Optional[str]) -> Dict[str, Any]:
        """Parse the raw document structure into sections."""
        structured_data = {
            'title': title,
            'source_platform': 'google_docs',
            'sections': {},
            'metadata': {
                'document_id': document_id,
                'last_modified': modified_time,
                'document_title': title,
                'total_elements': 0
            }
        }
        
        content = raw_document.get('body', {}).get('content', [])
        current_section = None
        element_count = 0
        
        for element in content:
            element_count += 1
            
            if 'paragraph' in element:
                section_data = self._parse_paragraph(element['paragraph'])
                if section_data:
                    section_type = section_data['type']
                    content_text = section_data['content']
                    
                    if section_type == 'heading':
                        current_section = content_text.lower().strip()
                        structured_data['sections'][current_section] = []
                    elif current_section and content_text:
                        structured_data['sections'][current_section].append(content_text)
            
            elif 'table' in element:
                # Handle tables if present
                table_content = self._parse_table(element['table'])
                if table_content and current_section:
                    structured_data['sections'][current_section].append(f"[Table]: {table_content}")
        
        structured_data['metadata']['total_elements'] = element_count
        structured_data['metadata']['sections_found'] = len(structured_data['sections'])
        
        return structured_data
    
    def _parse_paragraph(self, paragraph: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Parse individual paragraph element."""
        elements = paragraph.get('elements', [])
        content_parts = []
        
        for elem in elements:
            if 'textRun' in elem:
                text = elem['textRun']['content']
                # Preserve formatting indicators
                text_style = elem['textRun'].get('textStyle', {})
                if text_style.get('bold'):
                    text = f"**{text.strip()}**"
                elif text_style.get('italic'):
                    text = f"*{text.strip()}*"
                elif text_style.get('underline'):
                    text = f"__{text.strip()}__"
                
                if text.strip():
                    content_parts.append(text)
        
        if not content_parts:
            return None
        
        content = ' '.join(content_parts)
        
        # Detect paragraph type
        paragraph_style = paragraph.get('paragraphStyle', {})
        style_type = paragraph_style.get('namedStyleType', '')
        
        # Also check for list items
        bullet = paragraph.get('bullet', {})
        
        if style_type.startswith('HEADING'):
            return {'type': 'heading', 'content': content}
        elif bullet:
            return {'type': 'list_item', 'content': f"• {content}"}
        else:
            return {'type': 'content', 'content': content}
    
    def _parse_table(self, table: Dict[str, Any]) -> str:
        """Parse table element into text representation."""
        try:
            rows = []
            for row in table.get('tableRows', []):
                row_cells = []
                for cell in row.get('tableCells', []):
                    cell_text = []
                    for content in cell.get('content', []):
                        if 'paragraph' in content:
                            paragraph_data = self._parse_paragraph(content['paragraph'])
                            if paragraph_data:
                                cell_text.append(paragraph_data['content'])
                    row_cells.append(' '.join(cell_text))
                rows.append(' | '.join(row_cells))
            return '\n'.join(rows)
        except Exception:
            return "[Table content]"
    
    def _map_to_course_model(self, structured_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map parsed content to our course data model."""
        course_data = {
            'title': structured_data['title'],
            'course_description': '',
            'learning_outcomes': [],
            'assessment_formats': [],
            'tools': [],
            'lessons': [],
            'syllabus': structured_data['sections'],  # Keep raw sections for reference
            'metadata': structured_data['metadata']
        }
        
        # Process each section
        for section_name, content_list in structured_data['sections'].items():
            section_name_lower = section_name.lower()
            
            # First try exact handler matches
            handler_used = False
            for handler_key, handler in self.section_handlers.items():
                if handler_key in section_name_lower:
                    result = handler(content_list, section_name)
                    
                    # Map result to appropriate field
                    if handler_key in ['learning outcomes', 'objectives', 'learning objectives']:
                        course_data['learning_outcomes'] = result
                    elif 'assessment' in handler_key:
                        course_data['assessment_formats'] = result
                    elif 'tool' in handler_key:
                        course_data['tools'] = result
                    elif 'weekly' in handler_key or 'schedule' in handler_key:
                        course_data['lessons'] = result
                    elif 'description' in handler_key:
                        course_data['course_description'] = ' '.join(content_list) if isinstance(content_list, list) else str(content_list)
                    
                    handler_used = True
                    break
            
            # If no handler matched, use keyword detection
            if not handler_used:
                if any(keyword in section_name_lower for keyword in ['outcome', 'objective', 'goal']):
                    course_data['learning_outcomes'] = self._parse_learning_outcomes(content_list, section_name)
                elif any(keyword in section_name_lower for keyword in ['assessment', 'exam', 'test', 'assignment', 'grading']):
                    course_data['assessment_formats'] = self._parse_assessments(content_list, section_name)
                elif any(keyword in section_name_lower for keyword in ['tool', 'software', 'hardware', 'technology', 'resource']):
                    course_data['tools'] = self._parse_tools(content_list, section_name)
                elif any(keyword in section_name_lower for keyword in ['week', 'schedule', 'calendar', 'plan', 'lesson', 'module']):
                    course_data['lessons'] = self._parse_weekly_schedule(content_list, section_name)
                elif any(keyword in section_name_lower for keyword in ['description', 'overview', 'introduction']):
                    course_data['course_description'] = ' '.join(content_list) if isinstance(content_list, list) else str(content_list)
        
        # If no description found, try to get it from first content paragraph
        if not course_data['course_description'] and structured_data['sections']:
            first_section = next(iter(structured_data['sections'].values()), [])
            if first_section and len(first_section) > 0:
                # Use first non-empty content as description
                for item in first_section:
                    if item and len(item.strip()) > 10:  # Reasonable length for description
                        course_data['course_description'] = item.strip()
                        break
        
        return course_data
    
    def _parse_course_description(self, content_list: List[str], section_name: str) -> str:
        """Parse course description section."""
        if not content_list:
            return ""
        
        # Join all content items
        description = ' '.join(content_list)
        
        # Clean up formatting
        description = description.replace('**', '').replace('*', '').replace('__', '')
        
        return description.strip()
    
    def _parse_learning_outcomes(self, content_list: List[str], section_name: str) -> List[Dict[str, str]]:
        """Parse learning outcomes section."""
        outcomes = []
        
        for content in content_list:
            if not content or content.strip() == '':
                continue
            
            # Clean content
            content = content.replace('**', '').replace('*', '').replace('__', '').strip()
            
            # Pattern 1: "LO1: Description" or "Objective 1: Description"
            if ':' in content:
                parts = content.split(':', 1)
                code = parts[0].strip()
                description = parts[1].strip()
                
                # Extract number from code
                numbers = re.findall(r'\d+', code)
                number = numbers[0] if numbers else str(len(outcomes) + 1)
                
                outcomes.append({
                    'code': f"LO{number}",
                    'original_code': code,
                    'description': description,
                    'bloom_level': self._classify_bloom_level(description),
                    'assessment_type': self._suggest_assessment_type(description)
                })
            
            # Pattern 2: Numbered list "1. Description" or "- Description"
            elif content[0].isdigit() and '. ' in content[:10]:
                parts = content.split('. ', 1)
                if len(parts) == 2:
                    number = parts[0].strip()
                    description = parts[1].strip()
                    outcomes.append({
                        'code': f"LO{number}",
                        'original_code': number,
                        'description': description,
                        'bloom_level': self._classify_bloom_level(description),
                        'assessment_type': self._suggest_assessment_type(description)
                    })
            
            # Pattern 3: Bullet points starting with •, -, or *
            elif content.startswith(('•', '-', '*')):
                description = content[1:].strip()
                outcomes.append({
                    'code': f"LO{len(outcomes) + 1}",
                    'original_code': '',
                    'description': description,
                    'bloom_level': self._classify_bloom_level(description),
                    'assessment_type': self._suggest_assessment_type(description)
                })
            
            # Pattern 4: Plain text
            else:
                outcomes.append({
                    'code': f"LO{len(outcomes) + 1}",
                    'original_code': '',
                    'description': content,
                    'bloom_level': self._classify_bloom_level(content),
                    'assessment_type': self._suggest_assessment_type(content)
                })
        
        return outcomes
    
    def _classify_bloom_level(self, description: str) -> str:
        """Classify Bloom's taxonomy level based on description."""
        description_lower = description.lower()
        
        bloom_keywords = {
            'remember': ['define', 'describe', 'identify', 'label', 'list', 'match', 'name', 'recall', 'state'],
            'understand': ['explain', 'summarize', 'paraphrase', 'classify', 'compare', 'contrast', 'discuss', 'predict'],
            'apply': ['demonstrate', 'execute', 'implement', 'solve', 'use', 'illustrate', 'sketch', 'operate'],
            'analyze': ['analyze', 'differentiate', 'organize', 'attribute', 'deconstruct', 'integrate', 'correlate'],
            'evaluate': ['critique', 'evaluate', 'judge', 'justify', 'argue', 'defend', 'select', 'support'],
            'create': ['create', 'design', 'formulate', 'write', 'construct', 'develop', 'produce', 'plan']
        }
        
        for level, keywords in bloom_keywords.items():
            if any(keyword in description_lower for keyword in keywords):
                return level.capitalize()
        
        return 'Unknown'
    
    def _suggest_assessment_type(self, description: str) -> str:
        """Suggest assessment type based on learning outcome."""
        description_lower = description.lower()
        
        if any(word in description_lower for word in ['write', 'essay', 'report', 'paper', 'document']):
            return 'Written Assignment'
        elif any(word in description_lower for word in ['present', 'demo', 'demonstrate', 'show', 'exhibit']):
            return 'Presentation/Demo'
        elif any(word in description_lower for word in ['design', 'create', 'build', 'develop', 'produce']):
            return 'Project/Creation'
        elif any(word in description_lower for word in ['analyze', 'evaluate', 'critique', 'review', 'assess']):
            return 'Critical Analysis'
        elif any(word in description_lower for word in ['solve', 'calculate', 'compute', 'derive', 'formulate']):
            return 'Problem Solving'
        elif any(word in description_lower for word in ['discuss', 'debate', 'argue', 'defend', 'justify']):
            return 'Discussion/Debate'
        
        return 'General Assessment'
    
    def _parse_assessments(self, content_list: List[str], section_name: str) -> List[Dict[str, str]]:
        """Parse assessment formats section."""
        assessments = []
        
        for content in content_list:
            if not content or content.strip() == '':
                continue
            
            # Clean content
            content = content.replace('**', '').replace('*', '').replace('__', '').strip()
            
            assessment_type = self._classify_assessment_type(content)
            weight = self._extract_weight(content)
            due_info = self._extract_due_info(content)
            
            assessments.append({
                'type': assessment_type,
                'description': content,
                'requirements': content,
                'weight_percentage': weight,
                'due_info': due_info,
                'components': self._extract_assessment_components(content)
            })
        
        return assessments
    
    def _classify_assessment_type(self, content: str) -> str:
        """Classify assessment type based on content."""
        content_lower = content.lower()
        
        assessment_types = {
            'Written Assignment': ['written', 'essay', 'report', 'paper', 'article', 'document', 'thesis'],
            'Presentation': ['presentation', 'slide', 'demo', 'demonstration', 'talk', 'speech'],
            'Project': ['project', 'portfolio', 'collection', 'showcase', 'exhibition'],
            'Exam/Test': ['exam', 'test', 'quiz', 'midterm', 'final', 'assessment', 'evaluation'],
            'Lab/Exercise': ['lab', 'exercise', 'practice', 'worksheet', 'activity'],
            'Reflective Writing': ['reflective', 'journal', 'diary', 'log', 'blog', 'self-assessment'],
            'Group Work': ['group', 'team', 'collaborative', 'peer', 'pair'],
            'Code/Programming': ['code', 'program', 'script', 'algorithm', 'software', 'app']
        }
        
        for type_name, keywords in assessment_types.items():
            if any(keyword in content_lower for keyword in keywords):
                return type_name
        
        return 'Assignment'
    
    def _extract_weight(self, content: str) -> Optional[str]:
        """Extract weight percentage from assessment description."""
        # Look for patterns like "30%", "worth 40%", "weight: 25%"
        patterns = [
            r'(\d+)\s*%',
            r'worth\s*(\d+)\s*%',
            r'weight\s*[:\s]*(\d+)\s*%',
            r'(\d+)\s*percent'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return f"{match.group(1)}%"
        
        return None
    
    def _extract_due_info(self, content: str) -> Optional[str]:
        """Extract due date information."""
        # Look for patterns like "due Week 5", "submit by April 15", "deadline: Friday"
        patterns = [
            r'due\s*(week\s*\d+|[^,.;]+)',
            r'submit\s*(by|before)\s*([^,.;]+)',
            r'deadline\s*[:\s]*([^,.;]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_assessment_components(self, content: str) -> List[str]:
        """Extract assessment components."""
        components = []
        
        # Common assessment components
        common_components = ['rubric', 'guidelines', 'template', 'examples', 'submission', 'format', 'length', 'criteria']
        
        for component in common_components:
            if component in content.lower():
                components.append(component.capitalize())
        
        return components
    
    def _parse_tools(self, content_list: List[str], section_name: str) -> List[Dict[str, str]]:
        """Parse tools and software section."""
        tools = []
        
        for content in content_list:
            if not content or content.strip() == '':
                continue
            
            # Clean content
            content = content.replace('**', '').replace('*', '').replace('__', '').strip()
            
            # Classify tool category
            category = self._classify_tool_category(content)
            tool_name = self._extract_tool_name(content)
            
            tools.append({
                'category': category,
                'name': tool_name,
                'description': content,
                'required': 'required' in content.lower() or 'must' in content.lower(),
                'proficiency': self._extract_proficiency_level(content)
            })
        
        return tools
    
    def _classify_tool_category(self, content: str) -> str:
        """Classify tool category."""
        content_lower = content.lower()
        
        if any(hw_keyword in content_lower for hw_keyword in ['cpu', 'ram', 'gpu', 'ssd', 'hardware', 'computer', 'device']):
            return 'Hardware'
        elif any(ai_keyword in content_lower for ai_keyword in ['ai', 'chatgpt', 'copilot', 'dalle', 'midjourney', 'stable diffusion', 'machine learning']):
            return 'AI Tools'
        elif any(design_keyword in content_lower for design_keyword in ['adobe', 'photoshop', 'illustrator', 'figma', 'canva', 'blender', 'maya', 'sketch']):
            return 'Design Software'
        elif any(dev_keyword in content_lower for dev_keyword in ['vscode', 'pycharm', 'github', 'git', 'docker', 'python', 'javascript', 'sql']):
            return 'Development Tools'
        elif any(office_keyword in content_lower for office_keyword in ['office', 'word', 'excel', 'powerpoint', 'google docs', 'slides', 'sheets']):
            return 'Office Software'
        
        return 'Software'
    
    def _extract_tool_name(self, content: str) -> str:
        """Extract tool name from content."""
        # Remove bullet points and clean
        content = content.lstrip('•-* ')
        
        # For bullet points like "- Software: Blender, Adobe CC"
        if ':' in content:
            before_colon = content.split(':')[0].strip()
            # Check if it's a category or tool name
            if any(word in before_colon.lower() for word in ['software', 'tool', 'hardware', 'platform', 'application']):
                # Look for specific tool names after colon
                after_colon = content.split(':', 1)[1]
                tool_names = ['Blender', 'Adobe', 'Figma', 'Canva', 'ChatGPT', 'Copilot', 'DALL·E', 'Midjourney', 
                             'Runway', 'Photoshop', 'Illustrator', 'VSCode', 'Python', 'GitHub']
                
                for tool in tool_names:
                    if tool.lower() in after_colon.lower():
                        return tool
                
                # Return first tool mentioned after colon
                parts = after_colon.split(',')
                if parts:
                    return parts[0].strip()
            
            return before_colon
        
        # Look for specific tool names
        tool_names = ['Blender', 'Adobe', 'Figma', 'Canva', 'ChatGPT', 'Copilot', 'DALL·E', 'Midjourney', 
                     'Runway', 'Photoshop', 'Illustrator', 'VSCode', 'Python', 'GitHub']
        
        for tool in tool_names:
            if tool.lower() in content.lower():
                return tool
        
        # Return first few words as tool name
        words = content.split()
        if words:
            return ' '.join(words[:3])
        
        return content.strip()
    
    def _extract_proficiency_level(self, content: str) -> str:
        """Extract required proficiency level."""
        content_lower = content.lower()
        
        if any(level in content_lower for level in ['basic', 'beginner', 'introductory', 'fundamental']):
            return 'Basic'
        elif any(level in content_lower for level in ['intermediate', 'moderate', 'working knowledge']):
            return 'Intermediate'
        elif any(level in content_lower for level in ['advanced', 'expert', 'proficient', 'master']):
            return 'Advanced'
        
        return 'Not Specified'
    
    def _parse_weekly_schedule(self, content_list: List[str], section_name: str) -> List[Dict[str, Any]]:
        """Parse weekly schedule section."""
        lessons = []
        week_counter = 1
        
        for content in content_list:
            if not content or content.strip() == '':
                continue
            
            # Clean content
            content = content.replace('**', '').replace('*', '').replace('__', '').strip()
            
            # Try different parsing strategies
            lesson_data = None
            
            # Strategy 1: Markdown table format
            if '|' in content:
                lesson_data = self._parse_markdown_table_row(content, week_counter)
            
            # Strategy 2: Structured format with Week X: pattern
            elif content.lower().startswith('week'):
                lesson_data = self._parse_week_header(content, week_counter)
            
            # Strategy 3: Bullet points with topics
            elif content.startswith(('•', '-', '*')):
                lesson_data = self._parse_bullet_point(content, week_counter)
            
            # Strategy 4: Default fallback
            if not lesson_data:
                lesson_data = {
                    'week': week_counter,
                    'topic': f"Week {week_counter}",
                    'content': content,
                    'activities': ['TBD'],
                    'assignments': ['TBD'],
                    'readings': []
                }
            
            lessons.append(lesson_data)
            week_counter += 1
        
        return lessons
    
    def _parse_markdown_table_row(self, content: str, week_number: int) -> Optional[Dict[str, Any]]:
        """Parse markdown table row format."""
        parts = [part.strip() for part in content.split('|') if part.strip()]
        
        if len(parts) >= 4:
            try:
                week_from_content = int(parts[0]) if parts[0].isdigit() else week_number
            except:
                week_from_content = week_number
            
            return {
                'week': week_from_content,
                'topic': parts[1],
                'activities': self._extract_list_items(parts[2]),
                'assignments': self._extract_list_items(parts[3]),
                'readings': self._extract_list_items(parts[4]) if len(parts) > 4 else [],
                'notes': parts[5] if len(parts) > 5 else ''
            }
        
        return None
    
    def _parse_week_header(self, content: str, week_number: int) -> Dict[str, Any]:
        """Parse week header format like 'Week 1: Introduction to...'"""
        # Extract week number and topic
        week_pattern = r'week\s*(\d+)[:\s]*([^:]+)'
        match = re.search(week_pattern, content, re.IGNORECASE)
        
        if match:
            week_num = int(match.group(1))
            topic = match.group(2).strip()
        else:
            week_num = week_number
            topic = content.replace('Week', '').replace('week', '').replace(':', '').strip()
        
        return {
            'week': week_num,
            'topic': topic,
            'activities': [],
            'assignments': [],
            'readings': [],
            'content': content
        }
    
    def _parse_bullet_point(self, content: str, week_number: int) -> Dict[str, Any]:
        """Parse bullet point format."""
        content = content.lstrip('•-* ').strip()
        
        # Try to extract topic
        topic = content.split(':')[0] if ':' in content else content
        
        return {
            'week': week_number,
            'topic': topic,
            'activities': [],
            'assignments': [],
            'readings': [],
            'content': content
        }
    
    def _extract_list_items(self, text: str) -> List[str]:
        """Extract list items from text."""
        items = []
        
        # Split by commas, semicolons, or "and"
        parts = re.split(r'[,;]|\band\b', text)
        
        for part in parts:
            part = part.strip()
            if part:
                items.append(part)
        
        return items