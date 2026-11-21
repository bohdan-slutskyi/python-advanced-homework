output "instance_id" {
  value       = aws_instance.django.id
  description = "Instance to stop and start after approved deployment"
}
output "instance_public_ip" {
  value       = aws_instance.django.public_ip
  description = "Dynamic public IP; may change on Stop/Start"
}
output "instance_public_dns" {
  value       = aws_instance.django.public_dns
  description = "Dynamic public DNS"
}
