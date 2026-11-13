"""
app/core/exceptions.py — εξαιρέσεις που γίνονται απάντηση HTTP με δικό τους σώμα (όχι {"detail": ...}).

StudyEnded: τέλος μελέτης για συμμετέχοντα της ομάδας παρέμβασης (S19) -> 403 {"study_ended": true}, στο login και σε
κάθε αίτημα με token. Το PWA δείχνει την οθόνη τέλους· η απάντηση δεν έχει ημερομηνία ή άλλο στοιχείο.
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

STUDY_ENDED_BODY = {"study_ended": True}


class StudyEnded(Exception):
    pass


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StudyEnded)
    async def _study_ended(request: Request, exc: StudyEnded) -> JSONResponse:
        return JSONResponse(STUDY_ENDED_BODY, status_code=403)
