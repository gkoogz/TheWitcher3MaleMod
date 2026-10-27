// Engine ABI transport only; archived numerical services are excluded.
bool VerifyFile(const std::filesystem::path& path,const std::string& expected){
 HANDLE file=CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
 if(file==INVALID_HANDLE_VALUE)return false;
 BCRYPT_ALG_HANDLE algorithm=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;
 bool ok=BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)>=0;
 DWORD size=0,written=0;if(ok)ok=BCryptGetProperty(algorithm,BCRYPT_OBJECT_LENGTH,reinterpret_cast<PUCHAR>(&size),sizeof(size),&written,0)>=0;
 std::vector<UCHAR> object(size),buffer(1024*1024);std::array<UCHAR,32> digest{};
 if(ok)ok=BCryptCreateHash(algorithm,&hash,object.data(),size,nullptr,0,0)>=0;
 while(ok){DWORD count=0;if(!ReadFile(file,buffer.data(),DWORD(buffer.size()),&count,nullptr)){ok=false;break;}if(!count)break;ok=BCryptHashData(hash,buffer.data(),count,0)>=0;}
 if(ok)ok=BCryptFinishHash(hash,digest.data(),DWORD(digest.size()),0)>=0;
 if(hash)BCryptDestroyHash(hash);if(algorithm)BCryptCloseAlgorithmProvider(algorithm,0);CloseHandle(file);
 if(!ok)return false;
 static const char hex[]="0123456789abcdef";std::string actual;
 for(auto x:digest){actual+=hex[x>>4];actual+=hex[x&15];}
 return actual==expected;
}
bool VerifyExecutable(){wchar_t path[32768]{};return GetModuleFileNameW(nullptr,path,32768)&&VerifyFile(path,profile::executableSHA256);}
template<class T>T Function(const profile::Function& f){return reinterpret_cast<T>(engineBase+f.rva);}
bool CheckPrefixes(){
 auto* dos=reinterpret_cast<const IMAGE_DOS_HEADER*>(engineBase);
 if(dos->e_magic!=IMAGE_DOS_SIGNATURE)return false;
 auto* pe=reinterpret_cast<const IMAGE_NT_HEADERS64*>(engineBase+dos->e_lfanew);
 if(pe->Signature!=IMAGE_NT_SIGNATURE||pe->OptionalHeader.SizeOfImage!=profile::imageSize)return false;
 for(const auto* f:{&profile::registerGlobals,&profile::allocate,&profile::namePool,&profile::internName,&profile::constructFunction,&profile::rtti,&profile::registerFunction})
  if(std::memcmp(reinterpret_cast<const void*>(engineBase+f->rva),f->prefix.data(),f->prefix.size()))return false;
 return true;
}
void FinishParameters(void* frame){
 // Native zero-argument wrappers advance past the EndParam opcode as well.
 auto& code=*reinterpret_cast<unsigned char**>(static_cast<unsigned char*>(frame)+0x30);++code;
}
template<class T> void Parameter(void* frame,T& value){
 auto& code=*reinterpret_cast<unsigned char**>(static_cast<unsigned char*>(frame)+0x30);
 const auto opcode=*code++;
 auto* table=reinterpret_cast<NativeCallback*>(engineBase+profile::opcodeTableRVA);
 if(table[opcode])table[opcode](*static_cast<void**>(frame),frame,&value);
}
bool RegistryContains(void* registry,std::uint32_t nameID,void* function){
 // Actual RegisterGlobalFunction disassembly: bucket capacity/count at 40/44,
 // table at 60, nodes {name, function, hash, next} at 0/8/10/18.
 auto* bytes=static_cast<unsigned char*>(registry);
 const auto capacity=*reinterpret_cast<const std::uint32_t*>(bytes+0x40);
 const auto count=*reinterpret_cast<const std::uint32_t*>(bytes+0x44);
 if(!capacity||capacity>1000000||count>1000000)return false;
 auto** buckets=*reinterpret_cast<unsigned char***>(bytes+0x60);
 if(!buckets)return false;
 auto* node=buckets[nameID%capacity];
 for(std::uint32_t i=0;node&&i<=count;i++,node=*reinterpret_cast<unsigned char**>(node+0x18)){
  if(*reinterpret_cast<std::uint32_t*>(node)==nameID&&*reinterpret_cast<std::uint32_t*>(node+0x10)==nameID)
   return *reinterpret_cast<void**>(node+8)==function;
 }
 return false;
}
bool Register(const char* name,NativeCallback callback){
 struct Block {void* data;std::size_t size;};Block block{};
 Function<void(*)(Block*,std::size_t,std::size_t)>(profile::allocate)(&block,0xf8,0x10);
 if(!block.data||block.size<0xf8||block.size>4096)return false;
 std::memset(block.data,0,0xf8);
 void* pool=Function<void*(*)()>(profile::namePool)();
 // Actual game registration uses ASCII bytes. The pool hashes single bytes;
 // passing UTF-16 silently interns only the first character before its NUL.
 auto id=Function<std::uint32_t(*)(void*,const char*)>(profile::internName)(pool,name);
 if(!id)return false;
 auto* function=Function<void*(*)(void*,const std::uint32_t*,NativeCallback)>(profile::constructFunction)(block.data,&id,callback);
 if(!function)return false;
 // The engine RTTI registry owns the engine-allocated function for its lifetime.
 void* registry=Function<void*(*)()>(profile::rtti)();
 Function<void(*)(void*,void*)>(profile::registerFunction)(registry,function);
 return RegistryContains(registry,id,function);
}
