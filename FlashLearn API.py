from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uuid
from datetime import datetime

app = FastAPI(title="Flashcards API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Pydantic models
class FlashcardCreate(BaseModel):
    front_text: str
    back_text: str

class FlashcardUpdate(BaseModel):
    front: str
    back: str
    flagged: Optional[bool] = None

class FlashcardResponse(BaseModel):
    id: str
    front: str
    back: str
    created_at: datetime
    set_id: Optional[str] = None
    flagged: bool = False

class FlashcardSet(BaseModel):
    name: str
    flashcards: List[FlashcardResponse]

class SetAssignment(BaseModel):
    set_id: Optional[str] = None

class SetUpdate(BaseModel):
    name: str
    flashcard_count: int

# In-memory storage (use a database in production)
flashcards_db = {}
flashcard_sets_db = {}

@app.get("/")
async def root():
    return {"message": "Welcome to the Flashcards API"}

@app.post("/flashcards/create", response_model=List[FlashcardResponse])
async def create_flashcards(flashcard_text: str):
    """
    Create flashcards from text input.
    Format: Each line should be "front_text;back_text"
    Example:
    Which is the best baseball team of all time?;The Toronto Blue Jays
    """
    # Split by lines and clean up whitespace
    lines = [line.strip() for line in flashcard_text.split('\n') if line.strip()]
    
    if not lines:
        raise HTTPException(status_code=400, detail="No flashcard content found")
    
    created_flashcards = []
    sets_to_create = {}  # Track new sets to create
    
    for i, line in enumerate(lines):
        # Split each line by semicolon
        parts = line.split(';')
        if len(parts) < 2 or len(parts) > 3:
            raise HTTPException(
                status_code=400,
                detail=f"Line {i+1}: '{line}' - Each line must have format 'front;back' or 'front;back;set_name'"
            )
        
        front_text = parts[0].strip()
        back_text = parts[1].strip()
        set_name = parts[2].strip() if len(parts) == 3 else None
        
        if not front_text or not back_text:
            raise HTTPException(
                status_code=400,
                detail=f"Line {i+1}: Both front and back text must be non-empty"
            )
        
        # Handle set assignment
        set_id = None
        if set_name:
            # Check if set already exists
            existing_set = None
            for sid, sdata in flashcard_sets_db.items():
                if sdata["name"].lower() == set_name.lower():
                    existing_set = sid
                    break
            
            if existing_set:
                set_id = existing_set
            else:
                # Mark set for creation
                if set_name not in sets_to_create:
                    sets_to_create[set_name] = str(uuid.uuid4())
                set_id = sets_to_create[set_name]
        
        flashcard_id = str(uuid.uuid4())
        flashcard = FlashcardResponse(
            id=flashcard_id,
            front=front_text,
            back=back_text,
            created_at=datetime.now(),
            set_id=set_id,
            flagged=False
        )
        flashcards_db[flashcard_id] = flashcard
        created_flashcards.append(flashcard)
    
    # Create new sets
    for set_name, set_id in sets_to_create.items():
        flashcard_set = {
            "id": set_id,
            "name": set_name,
            "flashcard_ids": [],
            "flashcard_count": len([f for f in created_flashcards if f.set_id == set_id]),
            "created_at": datetime.now()
        }
        flashcard_sets_db[set_id] = flashcard_set
    
    return created_flashcards

@app.get("/flashcards", response_model=List[FlashcardResponse])
async def get_all_flashcards():
    """Get all flashcards"""
    return list(flashcards_db.values())

@app.get("/flashcards/flagged", response_model=List[FlashcardResponse])
async def get_flagged_flashcards():
    """Get all flagged flashcards"""
    return [flashcard for flashcard in flashcards_db.values() if flashcard.flagged]

@app.get("/flashcards/{flashcard_id}", response_model=FlashcardResponse)
async def get_flashcard(flashcard_id: str):
    """Get a specific flashcard by ID"""
    if flashcard_id not in flashcards_db:
        raise HTTPException(status_code=404, detail="Flashcard not found")
    return flashcards_db[flashcard_id]

@app.put("/flashcards/{flashcard_id}", response_model=FlashcardResponse)
async def update_flashcard(flashcard_id: str, flashcard: FlashcardUpdate):
    """Update a flashcard - accepts front/back format"""
    if flashcard_id not in flashcards_db:
        raise HTTPException(status_code=404, detail="Flashcard not found")
    
    existing_flashcard = flashcards_db[flashcard_id]
    updated_flashcard = FlashcardResponse(
        id=flashcard_id,
        front=flashcard.front,
        back=flashcard.back,
        created_at=existing_flashcard.created_at,
        set_id=existing_flashcard.set_id,
        flagged=flashcard.flagged if flashcard.flagged is not None else existing_flashcard.flagged
    )
    flashcards_db[flashcard_id] = updated_flashcard
    return updated_flashcard

@app.put("/flashcards/{flashcard_id}/assign-set", response_model=FlashcardResponse)
async def assign_flashcard_to_set(flashcard_id: str, assignment: SetAssignment):
    """Assign a flashcard to a set"""
    if flashcard_id not in flashcards_db:
        raise HTTPException(status_code=404, detail="Flashcard not found")
    
    # Validate set exists if set_id is provided
    if assignment.set_id and assignment.set_id not in flashcard_sets_db:
        raise HTTPException(status_code=404, detail="Flashcard set not found")
    
    flashcard = flashcards_db[flashcard_id]
    flashcard.set_id = assignment.set_id
    flashcards_db[flashcard_id] = flashcard
    
    return flashcard

@app.put("/flashcards/{flashcard_id}/toggle-flag", response_model=FlashcardResponse)
async def toggle_flashcard_flag(flashcard_id: str):
    """Toggle the flagged status of a flashcard"""
    if flashcard_id not in flashcards_db:
        raise HTTPException(status_code=404, detail="Flashcard not found")
    
    flashcard = flashcards_db[flashcard_id]
    flashcard.flagged = not flashcard.flagged
    flashcards_db[flashcard_id] = flashcard
    
    return flashcard

@app.delete("/flashcards/{flashcard_id}")
async def delete_flashcard(flashcard_id: str):
    """Delete a flashcard"""
    if flashcard_id not in flashcards_db:
        raise HTTPException(status_code=404, detail="Flashcard not found")
    del flashcards_db[flashcard_id]
    return {"message": "Flashcard deleted successfully"}

@app.post("/flashcard-sets", response_model=dict)
async def create_flashcard_set(name: str, flashcard_count: int):
    """Create a flashcard set - accepts name and count as query params"""
    set_id = str(uuid.uuid4())
    flashcard_set = {
        "id": set_id,
        "name": name,
        "flashcard_ids": [],  # Empty initially, flashcards will be assigned separately
        "flashcard_count": flashcard_count,
        "created_at": datetime.now()
    }
    flashcard_sets_db[set_id] = flashcard_set
    return {"id": set_id, "message": "Flashcard set created successfully"}

@app.get("/flashcard-sets/{set_id}", response_model=FlashcardSet)
async def get_flashcard_set(set_id: str):
    """Get a flashcard set with all its flashcards"""
    if set_id not in flashcard_sets_db:
        raise HTTPException(status_code=404, detail="Flashcard set not found")
    
    flashcard_set = flashcard_sets_db[set_id]
    # Get flashcards that belong to this set
    flashcards = [flashcard for flashcard in flashcards_db.values() if flashcard.set_id == set_id]
    
    return FlashcardSet(
        name=flashcard_set["name"],
        flashcards=flashcards
    )

@app.put("/flashcard-sets/{set_id}", response_model=dict)
async def update_flashcard_set(set_id: str, set_update: SetUpdate):
    """Update a flashcard set"""
    if set_id not in flashcard_sets_db:
        raise HTTPException(status_code=404, detail="Flashcard set not found")
    
    flashcard_set = flashcard_sets_db[set_id]
    flashcard_set["name"] = set_update.name
    flashcard_set["flashcard_count"] = set_update.flashcard_count
    flashcard_sets_db[set_id] = flashcard_set
    
    return {"id": set_id, "message": "Flashcard set updated successfully"}

@app.get("/flashcard-sets", response_model=List[dict])
async def get_all_flashcard_sets():
    """Get all flashcard sets"""
    return [
        {
            "id": set_id,
            "name": set_data["name"],
            "flashcard_count": len([flashcard for flashcard in flashcards_db.values() if flashcard.set_id == set_id]),
            "created_at": set_data["created_at"]
        }
        for set_id, set_data in flashcard_sets_db.items()
    ]

@app.delete("/flashcard-sets/{set_id}")
async def delete_flashcard_set(set_id: str):
    """Delete a flashcard set"""
    if set_id not in flashcard_sets_db:
        raise HTTPException(status_code=404, detail="Flashcard set not found")
    
    # Remove set_id from all flashcards in this set
    for flashcard in flashcards_db.values():
        if flashcard.set_id == set_id:
            flashcard.set_id = None
    
    del flashcard_sets_db[set_id]
    return {"message": "Flashcard set deleted successfully"}

@app.get("/flashcards/export", response_model=dict)
async def export_all_flashcards():
    """Export all flashcards in the format front;back;set_name"""
    export_lines = []
    
    for flashcard in flashcards_db.values():
        front = flashcard.front
        back = flashcard.back
        
        # Get set name if flashcard belongs to a set
        set_name = ""
        if flashcard.set_id and flashcard.set_id in flashcard_sets_db:
            set_name = flashcard_sets_db[flashcard.set_id]["name"]
        
        if set_name:
            export_lines.append(f"{front};{back};{set_name}")
        else:
            export_lines.append(f"{front};{back}")
    
    return {"export_text": "\n".join(export_lines)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)