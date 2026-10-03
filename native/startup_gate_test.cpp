#include "startup_gate.hpp"
#include <dinput.h>
#include <iostream>
#include <stdexcept>
namespace {malemod::witcher::StartupGate gate;int calls=0;
int WINAPI Enter(){++calls;auto original=reinterpret_cast<int(WINAPI*)()>(gate.Restore());if(!original)throw std::runtime_error("Cannot restore entry");return original();}}
int wmain(int argc,wchar_t** argv){try{
 auto page=VirtualAlloc(nullptr,4096,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE);if(!page)throw std::runtime_error("Allocate entry page");
 std::array<unsigned char,14> bytes{0xb8,42,0,0,0,0xc3,0x90,0x90,0x90,0x90,0x90,0x90,0x90,0x90};std::memcpy(page,bytes.data(),bytes.size());
 auto wrong=bytes;wrong[1]=43;if(gate.Arm(page,wrong,reinterpret_cast<void*>(&Enter)))throw std::runtime_error("Unknown entry accepted");
 if(!gate.Arm(page,bytes,reinterpret_cast<void*>(&Enter)))throw std::runtime_error("Cannot arm entry");
 auto entry=reinterpret_cast<int(WINAPI*)()>(page);
 if(entry()!=42||calls!=1||std::memcmp(page,bytes.data(),bytes.size()))throw std::runtime_error("Entry did not restore exactly");
 if(entry()!=42||calls!=1||gate.Restore())throw std::runtime_error("Startup executed twice");VirtualFree(page,0,MEM_RELEASE);
 std::cout<<"PASS: startup gate restores exact entry bytes before original execution; unknown entry rejected and startup occurs once\n";
 if(argc==2){
  auto library=LoadLibraryW(argv[1]);if(!library)throw std::runtime_error("Load startup proxy in SDK test");
  auto create=reinterpret_cast<HRESULT(WINAPI*)(HINSTANCE,DWORD,REFIID,LPVOID*,LPUNKNOWN)>(GetProcAddress(library,"DirectInput8Create"));
  IDirectInput8W* input=nullptr;if(!create||FAILED(create(GetModuleHandleW(nullptr),DIRECTINPUT_VERSION,IID_IDirectInput8W,reinterpret_cast<void**>(&input),nullptr))||!input)throw std::runtime_error("System DirectInput forwarding failed");
  input->Release();auto format=reinterpret_cast<LPCDIDATAFORMAT(WINAPI*)()>(GetProcAddress(library,"GetdfDIJoystick"));
  if(!format||!format()||format()->dwSize!=sizeof(DIDATAFORMAT))throw std::runtime_error("System data-format forwarding failed");
  FreeLibrary(library);std::cout<<"PASS: normal-startup proxy forwards actual system DirectInput creation and joystick data format\n";
 }
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
