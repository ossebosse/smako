"""Serialized zero-network retry of the unchanged current relay artifact."""
import asyncio,socket,time
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import event
from job import configure,save
configure();P=Path('/work')
from grocery_data import __main__ as cli
from grocery_data.app.services.source_artifact import import_source_inbox
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path
settings,engine,factory=cli._runtime();errors=[]
@event.listens_for(engine,'handle_error')
def capture(context):
 original=context.original_exception
 errors.append({'type':type(original).__name__,'sqlite_errorname':getattr(original,'sqlite_errorname',None),'sqlite_errorcode':getattr(original,'sqlite_errorcode',None),'message':str(original)[:200],'statement_prefix':context.statement[:90] if context.statement else None})
 save('relay-database-errors',errors)
def denied(*a,**k):raise AssertionError('network forbidden during source-artifact import')
start=time.monotonic()
with RefreshRunLock(production_refresh_lock_path(P/'grocery.sqlite',P/'price-universes')):
 with patch.object(socket,'getaddrinfo',denied):
  result=asyncio.run(import_source_inbox(factory,FilesystemRawSnapshotStore(P/'raw'),P/'raw/source-inbox/willys'))
save('relay-retry',{'result':result,'seconds':time.monotonic()-start,'database_errors':errors,'network_requests':0,'scope':'unchanged real 2026-09-27 capture, observations not advanced; no concurrent DB inspection'});print(result)
