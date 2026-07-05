import os
import json
import logging
from django.conf import settings
from django.core.files.base import ContentFile
from apps.exports.models import ExportJob
from apps.generator.models import GeneratedArtifact
from config.constants import EXPORT_FORMAT_MARKDOWN, EXPORT_FORMAT_PDF, EXPORT_FORMAT_JSON

logger = logging.getLogger('specpilot.ai')

class ExportService:
    """
    Business logic aggregator compiling project specifications into Markdown, PDF, or JSON.
    """

    @staticmethod
    def compile_markdown(project):
        """
        Gathers all completed artifacts in lifecycle order and compiles them into a single markdown string.
        """
        logger.info(f"Compiling Markdown blueprint for project '{project.title}'")
        
        # Load artifacts in lifecycle order
        artifacts = GeneratedArtifact.objects.filter(project=project).order_by('step__order')
        
        parts = [
            f"# SpecPilot AI Blueprint: {project.title}",
            f"**Architecture Style:** {project.get_target_architecture_display()}",
            f"**Description:** {project.description}",
            "\n---\n"
        ]
        
        for art in artifacts:
            parts.append(f"## Phase {art.step.order if art.step else 'X'}: {art.title}")
            parts.append(art.content)
            parts.append("\n---\n")
            
        return "\n".join(parts)

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
                            "content": art.content
                        }
                        for art in artifacts
                    ]
                }
                content_str = json.dumps(data, indent=2)
                file_name = f"{filename}.json"
                job.download_file.save(file_name, ContentFile(content_str.encode('utf-8')))
                
            elif export_format == EXPORT_FORMAT_PDF:
                # PDF building routine using ReportLab
                file_name = f"{filename}.pdf"
                file_path = os.path.join(export_dir, file_name)
                
                from reportlab.lib.pagesizes import letter
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                
                doc = SimpleDocTemplate(file_path, pagesize=letter)
                styles = getSampleStyleSheet()
                
                # Custom styles to fit dark/light modern formats
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
                    Paragraph(f"<b>Architecture:</b> {project.get_target_architecture_display()}", body_style),
                    Paragraph(f"<b>Scope Description:</b> {project.description}", body_style),
                    Spacer(1, 15)
                ]
                
                artifacts = GeneratedArtifact.objects.filter(project=project).order_by('step__order')
                for art in artifacts:
                    story.append(Paragraph(f"Phase {art.step.order if art.step else 'X'}: {art.title}", h2_style))
                    # Basic paragraph styling (converting markdown newlines to HTML breaks)
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
