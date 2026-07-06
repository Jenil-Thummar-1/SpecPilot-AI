import os
import json
import logging
import io
import zipfile
from django.conf import settings
from django.core.files.base import ContentFile
from apps.exports.models import ExportJob
from apps.generator.models import GeneratedArtifact
from config.constants import EXPORT_FORMAT_MARKDOWN, EXPORT_FORMAT_PDF, EXPORT_FORMAT_JSON, EXPORT_FORMAT_ZIP

logger = logging.getLogger('specpilot.ai')

class ExportService:
    """
    Business logic aggregator compiling project specifications into Markdown, PDF, JSON, or ZIP packages.
    """

    @staticmethod
    def compile_markdown(project):
        """
        Gathers all completed artifacts in lifecycle order and compiles them into a single markdown string.
        """
        logger.info(f"Compiling Markdown blueprint for project '{project.title}'")
        
        # Load latest artifact for each step in lifecycle order
        steps = project.plan.steps.all().order_by('order')
        artifacts = []
        for step in steps:
            art = step.generated_artifacts.order_by('-version').first()
            if art:
                artifacts.append(art)
        
        parts = [
            f"# SpecPilot AI Project Specification Blueprint: {project.title}",
            f"**Architecture Style:** {project.get_target_architecture_display()}",
            f"**Predefined Category/Template:** {project.get_category_display()}",
            f"**Elevator Pitch:** {project.short_description}",
            f"**Detailed Scope:** {project.description}",
            f"**Target Audience Personas:** {project.target_users}",
            f"**Preferred Technology Stack:** {project.tech_stack}",
            f"**Deployment Preference:** {project.deployment_preference}",
            f"**Workspace Current Version:** v{project.current_version}",
            "\n---\n"
        ]
        
        for art in artifacts:
            parts.append(f"## Phase {art.step.order if art.step else 'X'}: {art.title}")
            parts.append(art.content)
            parts.append("\n---\n")
            
        return "\n".join(parts)

    @classmethod
    def compile_zip(cls, project):
        """
        Bundles individual specification documents as markdown files inside a clean ZIP directory format.
        """
        logger.info(f"Packaging ZIP spec blueprint archives for project '{project.title}'")
        
        # Load latest artifact for each step in lifecycle order
        steps = project.plan.steps.all().order_by('order')
        artifacts = []
        for step in steps:
            art = step.generated_artifacts.order_by('-version').first()
            if art:
                artifacts.append(art)
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add project summary readme file
            summary = (
                f"# SpecPilot AI Blueprint Package: {project.title}\n"
                f"Description: {project.description}\n"
                f"Architecture Type: {project.get_target_architecture_display()}\n"
                f"Version: v{project.current_version}\n"
                f"Category Template: {project.get_category_display()}\n"
                f"Deployment Target: {project.deployment_preference}\n"
                f"Tech Stack: {project.tech_stack}\n"
            )
            zip_file.writestr("README.md", summary)
            
            # Package all generated files individually
            for art in artifacts:
                safe_title = "".join(c for c in art.title if c.isalnum() or c in (' ', '_', '-')).strip()
                filename = f"{art.step.order:02d}_{safe_title.replace(' ', '_')}_v{art.version}.md"
                zip_file.writestr(f"specifications/{filename}", art.content)
                
        zip_buffer.seek(0)
        return zip_buffer.getvalue()

    @classmethod
    def run_export_job(cls, project, export_format):
        """
        Executes and audits the blueprint export compilation process.
        """
        logger.info(f"Initiating {export_format} export job for project: {project.title}")
        
        job = ExportJob.objects.create(
            project=project,
            export_format=export_format,
            status='PROCESSING'
        )
        
        # Ensure media directory exists
        export_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
        os.makedirs(export_dir, exist_ok=True)
        
        try:
            filename = f"specpilot_blueprint_{project.id}_{int(job.created_at.timestamp())}"
            
            # Retrieve latest version artifacts for compile
            steps = project.plan.steps.all().order_by('order')
            artifacts = []
            for step in steps:
                art = step.generated_artifacts.order_by('-version').first()
                if art:
                    artifacts.append(art)
            
            if export_format == EXPORT_FORMAT_MARKDOWN:
                content = cls.compile_markdown(project)
                file_name = f"{filename}.md"
                job.download_file.save(file_name, ContentFile(content.encode('utf-8')))
                
            elif export_format == EXPORT_FORMAT_JSON:
                # Compile structural JSON data
                data = {
                    "project_id": project.id,
                    "title": project.title,
                    "description": project.description,
                    "target_architecture": project.target_architecture,
                    "compiled_at": str(job.created_at),
                    "blueprint_phases": [
                        {
                            "step_order": art.step.order if art.step else 0,
                            "title": art.title,
                            "artifact_type": art.artifact_type,
                            "content": art.content,
                            "version": art.version,
                            "is_approved": art.is_approved
                        }
                        for art in artifacts
                    ]
                }
                content_str = json.dumps(data, indent=2)
                file_name = f"{filename}.json"
                job.download_file.save(file_name, ContentFile(content_str.encode('utf-8')))
                
            elif export_format == EXPORT_FORMAT_ZIP:
                # Zip compilation
                zip_data = cls.compile_zip(project)
                file_name = f"{filename}.zip"
                job.download_file.save(file_name, ContentFile(zip_data))

            elif export_format == EXPORT_FORMAT_PDF:
                # PDF building routine using ReportLab
                file_name = f"{filename}.pdf"
                file_path = os.path.join(export_dir, file_name)
                
                from reportlab.lib.pagesizes import letter
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                import html
                import re
                
                doc = SimpleDocTemplate(
                    file_path,
                    pagesize=letter,
                    leftMargin=54,
                    rightMargin=54,
                    topMargin=54,
                    bottomMargin=54
                )
                styles = getSampleStyleSheet()
                
                title_style = ParagraphStyle(
                    'DocTitle',
                    parent=styles['Heading1'],
                    fontSize=22,
                    leading=26,
                    textColor='#4F46E5',  # Indigo primary
                    spaceAfter=15
                )
                h2_style = ParagraphStyle(
                    'DocSubTitle',
                    parent=styles['Heading2'],
                    fontSize=14,
                    leading=18,
                    textColor='#7C3AED',  # Violet accent
                    spaceBefore=15,
                    spaceAfter=10
                )
                body_style = ParagraphStyle(
                    'DocBody',
                    parent=styles['Normal'],
                    fontSize=9.5,
                    leading=13.5,
                    textColor='#1F2937',  # Charcoal
                    spaceAfter=8
                )
                code_style = ParagraphStyle(
                    'DocCode',
                    parent=styles['Normal'],
                    fontSize=8.5,
                    leading=11,
                    textColor='#0F172A',
                    fontName='Courier',
                    spaceAfter=6,
                    leftIndent=15
                )
                
                story = [
                    Paragraph(f"SpecPilot AI Project Blueprint: {project.title}", title_style),
                    Paragraph(f"<b>Category Template:</b> {project.get_category_display()}", body_style),
                    Paragraph(f"<b>Architecture:</b> {project.get_target_architecture_display()}", body_style),
                    Paragraph(f"<b>Scope Description:</b> {project.description}", body_style),
                    Paragraph(f"<b>Tech Stack:</b> {project.tech_stack}", body_style),
                    Spacer(1, 15)
                ]
                
                for art in artifacts:
                    story.append(Paragraph(f"Phase {art.step.order if art.step else 'X'}: {art.title}", h2_style))
                    paragraphs = art.content.split('\n')
                    for p in paragraphs:
                        stripped = p.strip()
                        if not stripped:
                            continue
                        
                        # XML escape to prevent ReportLab crash on < or &
                        escaped_p = html.escape(stripped)
                        
                        # Convert basic markdown constructs to ReportLab HTML tags
                        escaped_p = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', escaped_p)
                        escaped_p = re.sub(r'\*(.*?)\*', r'<i>\1</i>', escaped_p)
                        escaped_p = re.sub(r'`(.*?)`', r'<font name="Courier">\1</font>', escaped_p)
                        
                        # Handle headers inside document content
                        if stripped.startswith('### '):
                            header_text = html.escape(stripped[4:])
                            story.append(Paragraph(f"<b>{header_text}</b>", body_style))
                        elif stripped.startswith('## '):
                            header_text = html.escape(stripped[3:])
                            story.append(Paragraph(f"<b>{header_text}</b>", body_style))
                        elif stripped.startswith('# '):
                            header_text = html.escape(stripped[2:])
                            story.append(Paragraph(f"<b>{header_text}</b>", body_style))
                        elif stripped.startswith('- ') or stripped.startswith('* '):
                            bullet_text = escaped_p[2:]
                            story.append(Paragraph(f"&bull; {bullet_text}", body_style))
                        elif stripped.startswith('1. ') or re.match(r'^\d+\.\s', stripped):
                            num_match = re.match(r'^(\d+\.\s)(.*)', escaped_p)
                            if num_match:
                                story.append(Paragraph(f"{num_match.group(1)}{num_match.group(2)}", body_style))
                            else:
                                story.append(Paragraph(escaped_p, body_style))
                        elif stripped.startswith('>') or stripped.startswith('    ') or stripped.startswith('\t'):
                            story.append(Paragraph(escaped_p, code_style))
                        else:
                            story.append(Paragraph(escaped_p, body_style))
                    story.append(Spacer(1, 10))
                
                # Draw custom headers and footers on PDF template pages
                def draw_page_decorations(canvas, doc_template):
                    canvas.saveState()
                    # Top header
                    canvas.setFont("Helvetica-Bold", 8)
                    canvas.setFillColor('#6B7280') # gray-500
                    canvas.drawString(54, 750, f"SpecPilot AI - Project Blueprint: {project.title}")
                    
                    # Top header divider line
                    canvas.setStrokeColor('#E5E7EB')
                    canvas.setLineWidth(0.5)
                    canvas.line(54, 742, letter[0] - 54, 742)
                    
                    # Bottom footer
                    canvas.setFont("Helvetica", 8)
                    canvas.setFillColor('#6B7280')
                    canvas.drawString(54, 36, "Confidential - For Review Only")
                    canvas.drawRightString(letter[0] - 54, 36, f"Page {doc_template.page}")
                    canvas.restoreState()
                    
                doc.build(story, onFirstPage=None, onLaterPages=draw_page_decorations)
                
                # Link the written file to the Django field
                with open(file_path, 'rb') as f:
                    job.download_file.save(file_name, ContentFile(f.read()), save=False)
            
            job.status = 'SUCCEEDED'
            job.save()
            logger.info(f"Export job {job.id} completed successfully.")
            return job
            
        except Exception as e:
            logger.error(f"Export compilation failed: {str(e)}")
            job.status = 'FAILED'
            job.error_message = str(e)
            job.save()
            return job
