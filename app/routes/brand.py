"""Brand asset repository — logos, colors, fonts, platform profiles, guidelines."""
import os
import shutil
import zipfile
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import (
    Project, BrandColor, BrandFont, BrandAsset, PlatformProfile, BrandGuidelines,
)

router = APIRouter(prefix="/brand")
templates = Jinja2Templates(directory="app/templates")

BRAND_DIR = os.path.expanduser("~/marketing-command-center/data/brand")


def _ensure_brand_dir(slug: str) -> str:
    path = os.path.join(BRAND_DIR, slug)
    os.makedirs(path, exist_ok=True)
    return path


@router.get("/")
def brand_page(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("brand.html", {
            "request": request, "project": None, "current_page": "brand",
            "today": date.today(),
        })

    pid = project.id
    colors = db.query(BrandColor).filter_by(project_id=pid).order_by(BrandColor.sort_order).all()
    fonts = db.query(BrandFont).filter_by(project_id=pid).order_by(BrandFont.sort_order).all()
    logos = db.query(BrandAsset).filter_by(project_id=pid, asset_type="logo").all()
    banners = db.query(BrandAsset).filter_by(project_id=pid, asset_type="banner").all()
    profiles = db.query(PlatformProfile).filter_by(project_id=pid).order_by(PlatformProfile.sort_order).all()
    guidelines = db.query(BrandGuidelines).filter_by(project_id=pid).first()

    return templates.TemplateResponse("brand.html", {
        "request": request,
        "project": project,
        "colors": colors,
        "fonts": fonts,
        "logos": logos,
        "banners": banners,
        "profiles": profiles,
        "guidelines": guidelines,
        "current_page": "brand",
        "today": date.today(),
    })


@router.post("/color/add")
def add_color(
    name: str = Form(...),
    hex_code: str = Form(...),
    usage_notes: str = Form(""),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("No project", status_code=400)
    count = db.query(BrandColor).filter_by(project_id=project.id).count()
    c = BrandColor(project_id=project.id, name=name, hex_code=hex_code, usage_notes=usage_notes, sort_order=count)
    db.add(c)
    db.commit()
    return HTMLResponse('<script>window.location.href="/brand";</script>')


@router.post("/color/delete/{color_id}")
def delete_color(color_id: int, db: Session = Depends(get_db)):
    c = db.get(BrandColor, color_id)
    if c:
        db.delete(c)
        db.commit()
    return HTMLResponse('<script>window.location.href="/brand";</script>')


@router.post("/font/add")
def add_font(
    name: str = Form(...),
    usage: str = Form(""),
    font_url: str = Form(""),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("No project", status_code=400)
    count = db.query(BrandFont).filter_by(project_id=project.id).count()
    f = BrandFont(project_id=project.id, name=name, usage=usage, font_url=font_url or None, sort_order=count)
    db.add(f)
    db.commit()
    return HTMLResponse('<script>window.location.href="/brand";</script>')


@router.post("/font/delete/{font_id}")
def delete_font(font_id: int, db: Session = Depends(get_db)):
    f = db.get(BrandFont, font_id)
    if f:
        db.delete(f)
        db.commit()
    return HTMLResponse('<script>window.location.href="/brand";</script>')


@router.post("/asset/upload")
async def upload_asset(
    request: Request,
    name: str = Form(...),
    asset_type: str = Form("logo"),
    platform: str = Form(""),
    dimensions: str = Form(""),
    usage_notes: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("No project", status_code=400)

    brand_path = _ensure_brand_dir(project.slug)
    ext = os.path.splitext(file.filename)[1] if file.filename else ".png"
    safe_name = name.lower().replace(" ", "_").replace("/", "_")
    filename = f"{asset_type}_{safe_name}{ext}"
    filepath = os.path.join(brand_path, filename)

    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    asset = BrandAsset(
        project_id=project.id,
        asset_type=asset_type,
        name=name,
        file_path=filepath,
        dimensions=dimensions or None,
        platform=platform or None,
        usage_notes=usage_notes,
    )
    db.add(asset)
    db.commit()
    return HTMLResponse('<script>window.location.href="/brand";</script>')


@router.post("/asset/delete/{asset_id}")
def delete_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = db.get(BrandAsset, asset_id)
    if asset:
        if asset.file_path and os.path.exists(asset.file_path):
            os.remove(asset.file_path)
        db.delete(asset)
        db.commit()
    return HTMLResponse('<script>window.location.href="/brand";</script>')


@router.post("/profile/add")
def add_profile(
    platform: str = Form(...),
    handle: str = Form(...),
    profile_url: str = Form(""),
    bio_text: str = Form(""),
    link: str = Form(""),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("No project", status_code=400)
    count = db.query(PlatformProfile).filter_by(project_id=project.id).count()
    p = PlatformProfile(
        project_id=project.id, platform=platform, handle=handle,
        profile_url=profile_url, bio_text=bio_text, link=link, sort_order=count,
    )
    db.add(p)
    db.commit()
    return HTMLResponse('<script>window.location.href="/brand";</script>')


@router.post("/profile/delete/{profile_id}")
def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    p = db.get(PlatformProfile, profile_id)
    if p:
        db.delete(p)
        db.commit()
    return HTMLResponse('<script>window.location.href="/brand";</script>')


@router.post("/guidelines/save")
def save_guidelines(
    voice_rules: str = Form(""),
    banned_words: str = Form(""),
    tone_description: str = Form(""),
    content_mix: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("No project", status_code=400)

    guidelines = db.query(BrandGuidelines).filter_by(project_id=project.id).first()
    if not guidelines:
        guidelines = BrandGuidelines(project_id=project.id)
        db.add(guidelines)

    guidelines.voice_rules = voice_rules
    guidelines.banned_words = banned_words
    guidelines.tone_description = tone_description
    guidelines.content_mix = content_mix
    guidelines.notes = notes
    db.commit()
    return HTMLResponse('<script>window.location.href="/brand";</script>')


@router.get("/download-all")
def download_all(db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("No project", status_code=400)

    assets = db.query(BrandAsset).filter_by(project_id=project.id).all()
    colors = db.query(BrandColor).filter_by(project_id=project.id).all()
    fonts = db.query(BrandFont).filter_by(project_id=project.id).all()
    profiles = db.query(PlatformProfile).filter_by(project_id=project.id).all()
    guidelines = db.query(BrandGuidelines).filter_by(project_id=project.id).first()

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add asset files
        for asset in assets:
            if asset.file_path and os.path.exists(asset.file_path):
                arcname = f"{asset.asset_type}/{os.path.basename(asset.file_path)}"
                zf.write(asset.file_path, arcname)

        # Brand info text file
        info = f"# {project.name} Brand Kit\n\n"
        info += "## Colors\n"
        for c in colors:
            info += f"- {c.name}: {c.hex_code} ({c.usage_notes})\n"
        info += "\n## Fonts\n"
        for f in fonts:
            info += f"- {f.name}: {f.usage}\n"
        info += "\n## Platform Profiles\n"
        for p in profiles:
            info += f"- {p.platform}: {p.handle}\n  Bio: {p.bio_text}\n  Link: {p.link}\n"
        if guidelines:
            info += f"\n## Voice & Tone\n{guidelines.voice_rules}\n"
            info += f"\n## Banned Words\n{guidelines.banned_words}\n"
            info += f"\n## Content Mix\n{guidelines.content_mix}\n"
        zf.writestr("brand-info.txt", info)

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={project.slug}-brand-kit.zip"},
    )
