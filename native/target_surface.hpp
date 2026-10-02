#pragma once
#include <malemod/surface/binding.hpp>
#include <malemod/surface/runtime.hpp>
#include <filesystem>
#include <memory>
#include <string>

namespace malemod::witcher {
// Geralt-specific lineage/rest bindings. Shared numerical laws are linked from
// Base. Native packed attributes, skinning and upload remain separate.
class TargetSurface {
 public:
  explicit TargetSurface(const std::filesystem::path&,const std::string& expectedBaseCommit);
  ~TargetSurface();
  std::vector<surface::PrecisePoint> Evaluate(unsigned lod,const surface::Output&);
  unsigned LODCount()const;
 private:
  struct Impl;std::unique_ptr<Impl> impl_;
};
}
