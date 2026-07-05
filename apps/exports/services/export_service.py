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
        
        # Load artifacts in lifecycle order
        artifacts = GeneratedArtifact.objects.filter(project=project, is_approved=True).order_by('step__order')
        if not artifacts.exists():
            artifacts = GeneratedArtifact.objects.filter(project=project).order_by('step__order')
        
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
        artifacts = GeneratedArtifact.objects.filter(project=project).order_by('step__order')
        
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
            
            if export_format == EXPORT_FORMAT_MARKDOWN:
                content = cls.compile_markdown(project)
                file_name = f"{filename}.md"
                job.download_file.save(file_name, ContentFile(content.encode('utf-8')))
                
            elif export_format == EXPORT_FORMAT_JSON:
                # Compile structural JSON data
                artifacts = GeneratedArtifact.objects.filter(project=project).order_by('step__order')
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
                
                doc = SimpleDocTemplate(file_path, pagesize=letter)
                styles = getSampleStyleSheet()
                
                title_style = ParagraphStyle(
                    'DocTitle',
                    parent=styles['Heading1'],
                    fontSize=24,
                    leading=28,
                    textColor='#4F46E5',  # Indigo primary
                    spaceAfter=15
                )
                h2_style = ParagraphStyle(
                    'DocSubTitle',
                    parent=styles['Heading2'],
                    fontSize=16,
                    leading=20,
                    textColor='#7C3AED',  # Violet accent
                    spaceBefore=15,
                    spaceAfter=10
                )
                body_style = ParagraphStyle(
                    'DocBody',
                    parent=styles['Normal'],
                    fontSize=10,
                    leading=14,
                    textColor='#1F2937',  # Charcoal
                    spaceAfter=10
                )
                
                story = [
                    Paragraph(f"SpecPilot AI Project Blueprint: {project.title}", title_style),
                    Paragraph(f"<b>Category Template:</b> {project.get_category_display()}", body_style),
                    Paragraph(f"<b>Architecture:</b> {project.get_target_architecture_display()}", body_style),
                    Paragraph(f"<b>Scope Description:</b> {project.description}", body_style),
                    Paragraph(f"<b>Tech Stack:</b> {project.tech_stack}", body_style),
                    Spacer(1, 15)
                ]
                
                artifacts = GeneratedArtifact.objects.filter(project=project).order_by('step__order')
                for art in artifacts:
                    story.append(Paragraph(f"Phase {art.step.order if art.step else 'X'}: {art.title}", h2_style))
                    paragraphs = art.content.split('\n')
                    for p in paragraphs:
                        if p.strip():
                            story.append(Paragraph(p.replace('\n', '<br/>'), body_style))
                    story.append(Spacer(1, 10))
                    
                doc.build(story)
                
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
